package registry

type Entry struct { Name string; Fields map[string]any; Policy map[string]any }

type Registry struct { Contracts []Entry }

func (r Registry) Names() []string {
 names := make([]string, 0, len(r.Contracts))
 for _, e := range r.Contracts { names = append(names, e.Name) }
 return names
}
