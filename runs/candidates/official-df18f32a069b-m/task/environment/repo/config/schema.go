package config

// Settings documents the stable configuration vocabulary consumed by the compiler.
type Settings struct {
 InputDirectory string
 OutputDirectory string
 AllowNullable bool
 RequireCompatibility bool
 Aliases map[string]string
 Exceptions map[string]string
}

func (s Settings) Effective() Settings {
 if s.Aliases == nil { s.Aliases = map[string]string{} }
 if s.Exceptions == nil { s.Exceptions = map[string]string{} }
 return s
}
