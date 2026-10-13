package main
import "bufio"
import "os"
func main(){s:=bufio.NewScanner(os.Stdin);for s.Scan(){os.Stdout.WriteString("{\"ok\":false,\"error\":\"service unavailable\"}\n")}}
