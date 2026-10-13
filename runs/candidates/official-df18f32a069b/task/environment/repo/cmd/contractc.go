package main

import "fmt"

type BuildNotice struct { Contract string; Accepted bool; Reason string }

func formatNotice(n BuildNotice) string {
 if n.Accepted { return fmt.Sprintf("accepted %s", n.Contract) }
 return fmt.Sprintf("rejected %s: %s", n.Contract, n.Reason)
}

func main() { fmt.Println(formatNotice(BuildNotice{Contract:"sample", Accepted:true})) }
