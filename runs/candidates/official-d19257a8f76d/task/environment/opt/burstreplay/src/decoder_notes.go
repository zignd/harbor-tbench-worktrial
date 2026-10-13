package replay

// The production decoder treats a logical record as a UTF-8 escaped stream.
// This placeholder documents the package boundary used by the shipped service.
type Event struct { Timestamp int64; Value int64; Weight int64 }
