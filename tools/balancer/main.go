package main

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"

	"golang.org/x/term"
)

var configH = func() string {
	_, file, _, _ := runtime.Caller(0)
	root := filepath.Dir(filepath.Dir(filepath.Dir(file)))
	return filepath.Join(root, "src", "config.h")
}()

// ANSI
const (
	reset  = "\033[0m"
	bold   = "\033[1m"
	dim    = "\033[2m"
	cyan   = "\033[96m"
	yellow = "\033[93m"
	green  = "\033[92m"
	red    = "\033[91m"
	clear  = "\033[2J\033[H"
)

type variable struct {
	name, cat  string
	min, max   int
}

var variables = []variable{
	{"GEAR1_MAX_SPEED",             "Car Physics", 1,  15},
	{"GEAR1_ACCEL",                 "Car Physics", 1,  15},
	{"GEAR2_MAX_SPEED",             "Car Physics", 1,  15},
	{"GEAR2_ACCEL",                 "Car Physics", 1,  15},
	{"GEAR3_MAX_SPEED",             "Car Physics", 1,  15},
	{"GEAR3_ACCEL",                 "Car Physics", 1,  15},
	{"GEAR_DOWNSHIFT_FRAMES",       "Car Physics", 1,  60},
	{"PLAYER_FRICTION",             "Car Physics", 0,   8},
	{"PLAYER_MAX_HP",               "Combat",      1, 255},
	{"PLAYER_ARMOR",                "Combat",      0,  15},
	{"DAMAGE_INVINCIBILITY_FRAMES", "Combat",      0,  60},
	{"ENEMY_BULLET_DAMAGE",         "Combat",      1,  99},
	{"PROJ_FIRE_COOLDOWN",          "Combat",      1,  60},
	{"PROJ_SPEED",                  "Combat",      1,  15},
	{"TURRET_FIRE_INTERVAL",        "Enemies",     1, 120},
	{"TURRET_HP",                   "Enemies",     1,  10},
}

var defineRe = regexp.MustCompile(`(?m)^#define\s+(\w+)\s+(\d+)u?`)
var replaceRe = regexp.MustCompile(`^(#define\s+(\w+)\s+)(\d+)(u?)(\s*.*)$`)

func parseConfig(text string) map[string]int {
	result := map[string]int{}
	for _, m := range defineRe.FindAllStringSubmatch(text, -1) {
		v, _ := strconv.Atoi(m[2])
		result[m[1]] = v
	}
	return result
}

func applyChanges(text string, changes map[string]int) string {
	lines := strings.Split(text, "\r\n")
	for i, line := range lines {
		m := replaceRe.FindStringSubmatch(line)
		if m == nil {
			continue
		}
		if v, ok := changes[m[2]]; ok {
			lines[i] = m[1] + strconv.Itoa(v) + m[4] + m[5]
		}
	}
	return strings.Join(lines, "\r\n")
}

func p(format string, a ...any) {
	fmt.Printf(format+"\r\n", a...)
}

func draw(vars []variable, values map[string]int, cursor int, status string) {
	fmt.Print(clear)
	p(bold + "Nuke Raider Balancer" + reset)
	lastCat := ""
	for i, v := range vars {
		if v.cat != lastCat {
			p(yellow+"%s"+reset, v.cat)
			lastCat = v.cat
		}
		val := values[v.name]
		arrow, style, end := " ", "", ""
		if i == cursor {
			arrow, style, end = "\u25b6", cyan+bold, reset
		}
		p("  %s%s %-28s [%3d]  %s(%d\u2013%d)%s%s",
			style, arrow, v.name, val, dim, v.min, v.max, reset, end)
	}
	hint := dim + "[\u2191\u2193] nav  [\u2190\u2192] change  [s] save  [q] quit" + reset
	if status != "" {
		col := green
		if !strings.HasPrefix(status, "Saved") {
			col = red
		}
		hint += "  " + col + status + reset
	}
	p("")
	p(hint)
}

func readKey(tty *os.File) string {
	buf := make([]byte, 3)
	n, _ := tty.Read(buf)
	if n == 0 {
		return ""
	}
	if buf[0] == 0x1b && n == 3 {
		switch string(buf[1:3]) {
		case "[A":
			return "UP"
		case "[B":
			return "DOWN"
		case "[C":
			return "RIGHT"
		case "[D":
			return "LEFT"
		}
	}
	return string(buf[:1])
}

func main() {
	text, err := os.ReadFile(configH)
	if err != nil {
		fmt.Fprintf(os.Stderr, "cannot read %s: %v\n", configH, err)
		os.Exit(1)
	}
	originalText := string(text)
	values := parseConfig(originalText)
	savedValues := map[string]int{}
	for k, v := range values {
		savedValues[k] = v
	}
	cursor := 0
	status := ""

	tty, err := os.OpenFile("/dev/tty", os.O_RDWR, 0)
	if err != nil {
		fmt.Fprintf(os.Stderr, "cannot open /dev/tty: %v\n", err)
		os.Exit(1)
	}
	defer tty.Close()

	oldState, err := term.MakeRaw(int(tty.Fd()))
	if err != nil {
		fmt.Fprintf(os.Stderr, "cannot set raw mode: %v\n", err)
		os.Exit(1)
	}
	defer term.Restore(int(tty.Fd()), oldState)

	draw(variables, values, cursor, status)

	for {
		key := readKey(tty)
		switch key {
		case "UP":
			if cursor > 0 {
				cursor--
			}
		case "DOWN":
			if cursor < len(variables)-1 {
				cursor++
			}
		case "LEFT", "RIGHT":
			v := variables[cursor]
			delta := -1
			if key == "RIGHT" {
				delta = 1
			}
			val := values[v.name] + delta
			if val < v.min {
				val = v.min
			}
			if val > v.max {
				val = v.max
			}
			values[v.name] = val
			status = ""
		case "s":
			changes := map[string]int{}
			for _, v := range variables {
				if values[v.name] != savedValues[v.name] {
					changes[v.name] = values[v.name]
				}
			}
			newText := applyChanges(originalText, changes)
			if err := os.WriteFile(configH, []byte(newText), 0644); err != nil {
				status = "Error: " + err.Error()
			} else {
				originalText = newText
				for k, v := range values {
					savedValues[k] = v
				}
				status = "Saved."
			}
		case "q", "\x03":
			term.Restore(int(tty.Fd()), oldState)
			unsaved := false
			for _, v := range variables {
				if values[v.name] != savedValues[v.name] {
					unsaved = true
					break
				}
			}
			if unsaved {
				fmt.Print("\033[2J\033[HUnsaved changes. Quit? [y/N] ")
				var ans string
				fmt.Scanln(&ans)
				if strings.ToLower(strings.TrimSpace(ans)) != "y" {
					term.MakeRaw(int(tty.Fd()))
					draw(variables, values, cursor, status)
					continue
				}
			}
			fmt.Print("\033[2J\033[H")
			fmt.Print("Build now? [y/N] ")
			var ans string
			fmt.Scanln(&ans)
			if strings.ToLower(strings.TrimSpace(ans)) == "y" {
				os.Exit(buildROM())
			}
			return
		}
		draw(variables, values, cursor, status)
	}
}

func buildROM() int {
	root := filepath.Dir(filepath.Dir(configH))
	cmd := fmt.Sprintf("cd %s && make clean && GBDK_HOME=/home/mathdaman/gbdk make", root)
	ret, _ := runShell(cmd)
	return ret
}

func runShell(cmd string) (int, error) {
	p, err := os.StartProcess("/bin/sh", []string{"sh", "-c", cmd},
		&os.ProcAttr{Files: []*os.File{os.Stdin, os.Stdout, os.Stderr}})
	if err != nil {
		return 1, err
	}
	state, err := p.Wait()
	if err != nil {
		return 1, err
	}
	return state.ExitCode(), nil
}
