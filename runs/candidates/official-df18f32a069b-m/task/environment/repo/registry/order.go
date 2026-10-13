package registry

import "sort"
func SortEntries(in []Entry) []Entry { out:=append([]Entry(nil),in...); sort.Slice(out,func(i,j int)bool{return out[i].Name<out[j].Name}); return out }
func Find(r Registry,name string)(Entry,bool){ for _,e:=range r.Contracts {if e.Name==name{return e,true}}; return Entry{},false }
func UniqueNames(r Registry) bool { seen:=map[string]bool{}; for _,e:=range r.Contracts {if seen[e.Name]{return false};seen[e.Name]=true};return true }
func Clone(r Registry) Registry { out:=Registry{Contracts:make([]Entry,len(r.Contracts))}; copy(out.Contracts,r.Contracts); return out }
