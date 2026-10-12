A regression in the `framecodec` service has been reported by a downstream user. The service runs on port 7000 inside this container. It accepts POST requests to `/decode` with a raw binary body and returns a JSON object with fields `type`, `seq`, and `payload` decoded from the frame. It also accepts POST to `/encode` with a JSON body `{"type": N, "seq": N, "payload": "<hex>"}` and returns the raw binary frame as the response body.

The wire format is: one byte for frame type, four bytes for sequence number (big-endian unsigned 32-bit integer), two bytes for payload length (big-endian unsigned 16-bit integer), followed by that many bytes of payload. The `/decode` endpoint must return `payload` as a lowercase hex string. A frame with a zero-length payload must decode successfully and return `payload` as an empty string `""`.

The `seq` field must be decoded and returned as a big-endian unsigned 32-bit integer. Encoding a message and then decoding the result must reproduce the original `type`, `seq`, and `payload` exactly for all valid inputs.

The service is not currently running. The source is at `/app/framecodec/`. A startup script is at `/app/start.sh`. After fixing any defects in the source, rebuild and restart the service so it is answering requests on port 7000.
