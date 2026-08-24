// Package highlight — BiuBiuBiu 语法高亮（渲染层用）。
//
// 简易实现：正则分词（关键字/字符串/数字/注释/类型/流名），输出 Fyne
// RichText 段。与 Python 功能层 lexer 的 Token 语义对齐（29+2 关键字）。
package highlight

import (
	"regexp"
	"strings"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/widget"
)

var (
	kwRe = regexp.MustCompile(`\b(program|Main|Stream|Class|Interface|implements|const|thread|need|res|ref|get|cause|ALL|if|else|while|for|break|continue|new|this|void|int|float|double|string|char|bool|true|false)\b`)
	strRe = regexp.MustCompile(`"(\\.|[^"\\])*"|'(\\.|[^'\\])*'`)
	numRe = regexp.MustCompile(`\b\d+(\.\d+)?\b`)
	comRe = regexp.MustCompile(`//[^\n]*|/\*.*?\*/`)
	typRe = regexp.MustCompile(`\b(CIO|FIO|SIO|IO|Com|Time|Obj|Solid|Arrays|Ref|Threads|Taskm|Array|Vector|SolidData)\b`)
)

// Highlight 把源码转为 Fyne RichText（带颜色）。
func Highlight(src string) *widget.RichText {
	rt := widget.NewRichText()
	pos := 0
	// 注释优先（避免注释内的关键字被着色）
	type span struct{ start, end int }
	var comments []span
	for _, m := range comRe.FindAllStringIndex(src, -1) {
		comments = append(comments, span{m[0], m[1]})
	}
	ci := 0

	appendSeg := func(text string, color fyne.ThemeColorName) {
		if text == "" {
			return
		}
		rt.Segments = append(rt.Segments, &widget.TextSegment{
			Text: text,
			Style: widget.RichTextStyle{
				ColorName: color,
			},
		})
	}

	for pos < len(src) {
		// 注释段
		if ci < len(comments) && pos == comments[ci].start {
			end := comments[ci].end
			appendSeg(src[pos:end], fyne.ThemeColorName("comment"))
			pos = end
			ci++
			continue
		}
		// 找下一个特殊 token 的起点
		next := len(src)
		kind := ""
		for _, entry := range []struct {
			re   *regexp.Regexp
			kind string
		}{
			{strRe, "string"}, {numRe, "number"}, {kwRe, "keyword"}, {typRe, "type"},
		} {
			if loc := entry.re.FindStringIndex(src[pos:]); loc != nil {
				if pos+loc[0] < next {
					next = pos + loc[0]
					kind = entry.kind
				}
			}
		}
		// 注释可能插在中间
		if ci < len(comments) && comments[ci].start < next {
			next = comments[ci].start
			kind = "comment"
		}
		if kind == "" {
			appendSeg(src[pos:], fyne.ThemeColorName("foreground"))
			break
		}
		if next > pos {
			appendSeg(src[pos:next], fyne.ThemeColorName("foreground"))
		}
		// token 本体
		re := kwRe
		switch kind {
		case "string":
			re = strRe
		case "number":
			re = numRe
		case "comment":
			re = comRe
		case "type":
			re = typRe
		}
		loc := re.FindStringIndex(src[next:])
		if loc == nil {
			appendSeg(src[next:], fyne.ThemeColorName("foreground"))
			break
		}
		end := next + loc[1]
		appendSeg(src[next:end], colorFor(kind))
		pos = end
	}
	rt.Wrapping = fyne.TextWrapWord
	return rt
}

func colorFor(kind string) fyne.ThemeColorName {
	switch kind {
	case "keyword":
		return fyne.ThemeColorName("primary")
	case "string":
		return fyne.ThemeColorName("success")
	case "number":
		return fyne.ThemeColorName("warning")
	case "comment":
		return fyne.ThemeColorName("disabled")
	case "type":
		return fyne.ThemeColorName("primary")
	}
	return fyne.ThemeColorName("foreground")
}

// Keywords 返回全部关键字（供补全/统计）。
func Keywords() []string {
	s := kwRe.String()
	s = strings.TrimPrefix(s, `\b(`)
	s = strings.TrimSuffix(s, `)\b`)
	return strings.Split(s, "|")
}
