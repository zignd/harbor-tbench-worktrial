package sketch

import "sort"

type Sketch struct{ values []float64 }

func (s *Sketch) Add(v float64) {
	if v > 0 {
		s.values = append(s.values, v)
	}
}
func (s *Sketch) Quantile(q float64) float64 {
	if len(s.values) == 0 {
		return 0
	}
	a := append([]float64(nil), s.values...)
	sort.Float64s(a)
	if q <= 0 {
		return a[0]
	}
	if q >= 1 {
		return a[len(a)-1]
	}
	p := q * float64(len(a)-1)
	i := int(p)
	if i+1 >= len(a) {
		return a[i]
	}
	return a[i] + (a[i+1]-a[i])*(p-float64(i))
}
