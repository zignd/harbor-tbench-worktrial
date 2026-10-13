package parser

import "sort"

type Path struct { File string; Name string }
func SortPaths(in []Path) []Path { out:=append([]Path(nil),in...); sort.Slice(out,func(i,j int)bool { if out[i].Name==out[j].Name{return out[i].File<out[j].File}; return out[i].Name<out[j].Name }); return out }
func CopyFields(in map[string]Field) map[string]Field { out:=make(map[string]Field,len(in)); for k,v:=range in { out[k]=v }; return out }
func Overlay(parent, child map[string]Field) map[string]Field { out:=CopyFields(parent); for k,v:=range child { out[k]=v }; return out }
func HasNullable(m map[string]Field) bool { for _,f:=range m { if f.Nullable!=nil && *f.Nullable{return true} }; return false }
