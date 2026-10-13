A regression in the `framecodec` service has been reported by a downstream user. The service is located at `/app/framecodec/` and, once running, listens on port 7000. It accepts POST requests to `/decode` with a raw binary body and returns a JSON object with fields `type`, `seq`, and `payload` decoded from the frame. It also accepts POST to `/encode` with a JSON body `{"type": N, "seq": N, "payload": "<hex>"}` and returns the raw binary frame as the response body.

The wire format for a frame is: one byte frame type, four bytes sequence number big-endian, two bytes payload length big-endian, followed by that many payload bytes.

After the regression the service misbehaves. Your job is to restore it so that every valid frame round-trips correctly: encoding a message and then decoding the result must reproduce the original `type`, `seq`, and `payload` exactly. The `seq` field must be decoded as a big-endian unsigned 32-bit integer. A frame whose payload length field encodes a value of zero must decode to an empty payload string `""` rather than returning an error.

A startup script is available at `/app/start.sh` that builds the project and starts the service. The service must be answering requests on port 7000 when verification runs.
