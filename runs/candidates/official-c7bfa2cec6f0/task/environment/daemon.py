import base64, json, math, socketserver, struct, subprocess

PORT = 7077


def crc16(data):
    c = 0xffff
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xffff if c & 0x8000 else (c << 1) & 0xffff
    return c


def integer(v):
    return isinstance(v, int) and not isinstance(v, bool)


def eigensystem(matrix):
    n = len(matrix)
    if n == 0:
        return [], []
    a = [row[:] for row in matrix]
    v = [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
    for _ in range(max(1, 100 * n * n)):
        p = q = 0
        best = 0.0
        for i in range(n):
            for j in range(i + 1, n):
                if abs(a[i][j]) > best:
                    best, p, q = abs(a[i][j]), i, j
        if best <= 1e-15:
            break
        phi = 0.25 * math.pi if abs(a[p][p] - a[q][q]) < 1e-30 else 0.5 * math.atan2(2 * a[p][q], a[p][p] - a[q][q])
        c, s = math.cos(phi), math.sin(phi)
        for i in range(n):
            if i not in (p, q):
                aip, aiq = a[i][p], a[i][q]
                a[i][p] = a[p][i] = c * aip - s * aiq
                a[i][q] = a[q][i] = s * aip + c * aiq
        app, aqq, apq = a[p][p], a[q][q], a[p][q]
        a[p][p] = c*c*app - 2*s*c*apq + s*s*aqq
        a[q][q] = s*s*app + 2*s*c*apq + c*c*aqq
        a[p][q] = a[q][p] = 0.0
        for i in range(n):
            vip, viq = v[i][p], v[i][q]
            v[i][p] = c * vip - s * viq
            v[i][q] = s * vip + c * viq
    order = sorted(range(n), key=lambda k: a[k][k], reverse=True)
    values, columns = [], []
    for k in order:
        col = [v[i][k] for i in range(n)]
        norm = math.sqrt(sum(x*x for x in col))
        col = [x / norm for x in col]
        pivot = max(range(n), key=lambda i: abs(col[i]))
        if col[pivot] < 0:
            col = [-x for x in col]
        values.append(a[k][k])
        columns.append(col)
    return values, columns


class Run:
    def __init__(self, obj):
        self.run_id = obj['run_id']
        self.channels = obj['channels']
        self.calibration = obj['calibration']
        self.requested_modes = obj['modes']
        self.modes = min(obj['modes'], obj['channels'])
        self.frames = {}
        self.corrections = {}
        self.rejected = 0
        self.duplicates = 0
        self.report_cache = None

    def add_frame(self, obj):
        if not integer(obj.get('seq')) or obj['seq'] < 0 or not isinstance(obj.get('data'), str):
            self.rejected += 1
            return {'ok': False, 'error': 'BAD_FRAME'}
        try:
            raw = base64.b64decode(obj['data'], validate=True)
            if len(raw) != self.channels * 2 + 2:
                raise ValueError
            values, got = raw[:-2], struct.unpack('<H', raw[-2:])[0]
            if crc16(values) != got:
                raise ValueError
            decoded = list(struct.unpack('<%dh' % self.channels, values))
        except Exception:
            self.rejected += 1
            return {'ok': False, 'error': 'BAD_FRAME'}
        if obj['seq'] in self.frames:
            self.duplicates += 1
        self.frames[obj['seq']] = decoded
        return {'ok': True, 'accepted': True, 'seq': obj['seq']}

    def add_correction(self, obj):
        seq = obj.get('seq')
        vals = obj.get('corrections')
        if not integer(seq) or seq < 0 or not isinstance(vals, list) or len(vals) != self.channels:
            return {'ok': False, 'error': 'INVALID'}
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(float(x)) for x in vals):
            return {'ok': False, 'error': 'INVALID'}
        self.corrections[seq] = [float(x) for x in vals]
        return {'ok': True, 'op': 'correction'}

    def finalize(self):
        observations = []
        for seq in sorted(self.frames):
            corrected = [self.frames[seq][i] + self.corrections.get(seq, [0.0] * self.channels)[i] for i in range(self.channels)]
            packed = struct.pack('<IHH', self.calibration, self.channels, self.modes)
            # The native interface consumes signed int16 channel values.
            vals = [max(-32768, min(32767, int(round(x)))) for x in corrected]
            packed += struct.pack('<%dh' % self.channels, *vals)
            out = subprocess.check_output(['/usr/local/libexec/modalcodec'], input=packed)
            observations.append(list(struct.unpack('<%dd' % self.modes, out)))
        d = self.modes
        n = len(observations)
        mean = [sum(row[j] for row in observations) / n if n else 0.0 for j in range(d)]
        covariance = [[sum((row[i]-mean[i])*(row[j]-mean[j]) for row in observations) / (n-1) if n > 1 else 0.0 for j in range(d)] for i in range(d)]
        values, vectors = eigensystem(covariance)
        values = [0.0 if -1e-10 < x < 0 else x for x in values]
        seqs = sorted(self.frames)
        missing = seqs[-1] - seqs[0] + 1 - len(seqs) if seqs else 0
        return {'run_id': self.run_id, 'calibration': self.calibration,
                'counts': {'accepted': len(seqs), 'rejected': self.rejected, 'duplicate': self.duplicates, 'missing': missing},
                'mean': mean, 'covariance': covariance, 'eigenvalues': values, 'eigenvectors': vectors}


class Handler(socketserver.StreamRequestHandler):
    def handle(self):
        runs = {}
        for line in self.rfile:
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    raise ValueError('JSON')
                op = obj.get('op')
                rid = obj.get('run_id')
                if not isinstance(rid, str) or not rid:
                    raise ValueError('INVALID')
                run = runs.get(rid)
                if op == 'begin':
                    if run is not None:
                        raise ValueError('ORDER')
                    if not all(integer(obj.get(k)) for k in ('channels', 'calibration', 'modes')) or obj['channels'] <= 0 or obj['modes'] <= 0 or obj['calibration'] not in (1, 2, 3):
                        raise ValueError('INVALID')
                    runs[rid] = Run(obj)
                    response = {'ok': True, 'op': 'begin'}
                elif run is None:
                    raise ValueError('UNKNOWN_RUN')
                elif op == 'frame' and run.report_cache is None:
                    response = run.add_frame(obj)
                elif op == 'correction' and run.report_cache is None:
                    response = run.add_correction(obj)
                elif op == 'finalize' and run.report_cache is None:
                    run.report_cache = run.finalize()
                    response = {'ok': True, 'report': run.report_cache}
                elif op == 'query' and run.report_cache is not None:
                    response = {'ok': True, 'report': run.report_cache}
                else:
                    raise ValueError('ORDER')
            except ValueError as exc:
                response = {'ok': False, 'error': str(exc)}
            except Exception:
                response = {'ok': False, 'error': 'INVALID'}
            self.wfile.write((json.dumps(response, separators=(',', ':')) + '\n').encode())
            self.wfile.flush()


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


if __name__ == '__main__':
    with Server(('0.0.0.0', PORT), Handler) as server:
        server.serve_forever()
