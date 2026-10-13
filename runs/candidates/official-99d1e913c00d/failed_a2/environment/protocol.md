Beacon Catalog Protocol

Requests and responses are one JSON object per line. Successful lookup is {"ok":true,"device":D,"value":number,"quality":string,"source_seq":integer}. Successful history is {"ok":true,"device":D,"records":[{"at":integer,"value":number,"quality":string,"source_seq":integer}]}. Successful stats is {"ok":true,"records":integer,"devices":integer,"rejected":integer,"generation":string}. Successful reload is {"ok":true,"generation":string}. Errors are {"ok":false,"error":string}. History endpoints are inclusive.
