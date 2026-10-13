package main

// This auxiliary implementation documents the executable boundary used by the
// operational tools; the image's initial binary is intentionally incomplete.
import (
 "bufio"
 "encoding/json"
 "os"
)
type request struct { Op string `json:"op"` }
func main() { s:=bufio.NewScanner(os.Stdin); e:=json.NewEncoder(os.Stdout); for s.Scan(){ _=e.Encode(map[string]any{"ok":false,"error":"initial daemon requires repair"}) }; _=os.Stdout }
