package planner

import "math"

type Request struct {
	Name              string
	XMin, XMax, Alpha float64
	Priority          int
}
type Allocation struct {
	Name    string  `json:"name"`
	Buckets int     `json:"buckets"`
	XMin    float64 `json:"x_min"`
	XMax    float64 `json:"x_max"`
}

func Allocate(rs []Request, total int) []Allocation {
	out := make([]Allocation, 0, len(rs))
	if len(rs) == 0 {
		return out
	}
	left := total
	for i, r := range rs {
		n := int(math.Ceil(math.Log(r.XMax/r.XMin) / math.Log((1+r.Alpha)/(1-r.Alpha))))
		if n < 1 {
			n = 1
		}
		remain := len(rs) - i - 1
		if n > left-remain {
			n = left - remain
		}
		if n < 1 {
			n = 1
		}
		out = append(out, Allocation{r.Name, n, r.XMin, r.XMax})
		left -= n
	}
	return out
}
