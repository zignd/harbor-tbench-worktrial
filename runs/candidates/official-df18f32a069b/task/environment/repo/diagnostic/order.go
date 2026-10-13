package diagnostic

import "sort"
func Sort(in []Event) []Event { out:=append([]Event(nil),in...); sort.Slice(out,func(i,j int)bool {if out[i].Contract==out[j].Contract{return out[i].Reason<out[j].Reason};return out[i].Contract<out[j].Contract});return out }
func Group(in []Event) map[string][]Event { out:=map[string][]Event{}; for _,e:=range in {out[e.Contract]=append(out[e.Contract],e)};return out }
func Count(in []Event) int { return len(in) }
