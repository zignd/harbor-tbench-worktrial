package config

import "strings"

type Value struct { Present bool; Text string }
func NewValue(s string) Value { return Value{Present:true, Text:s} }
func (v Value) Bool(def bool) bool { if !v.Present { return def }; return strings.EqualFold(v.Text,"true") }
func (v Value) Empty() bool { return !v.Present || v.Text=="" }
func Merge(base, local map[string]Value) map[string]Value { out:=map[string]Value{}; for k,v:=range base { out[k]=v }; for k,v:=range local { out[k]=v }; return out }
func Keys(m map[string]Value) []string { out:=make([]string,0,len(m)); for k:=range m { out=append(out,k) }; return out }
