package diagnostic

type Event struct { Contract string; Reason string }

func (e Event) Valid() bool { return e.Contract != "" && e.Reason != "" }
