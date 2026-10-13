package parser

import "encoding/json"

type Field struct { Type string `json:"type"`; Nullable *bool `json:"nullable,omitempty"` }
type Document struct { Name string `json:"name"`; Parent string `json:"parent,omitempty"`; Fields map[string]Field `json:"fields"`; Policy map[string]any `json:"policy"` }

func Decode(data []byte) (Document, error) {
 var d Document
 err := json.Unmarshal(data, &d)
 return d, err
}
