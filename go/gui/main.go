// Command gui — Biol.Studio 渲染层（Fyne GUI）。
//
// 视图：项目树 + 多标签编辑器 + 输出面板 + 示例画廊。
// 业务：直接调用 internal/biolang（与通讯层同一套逻辑）。
package main

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/app"
	"fyne.io/fyne/v2/container"
	"fyne.io/fyne/v2/dialog"
	"fyne.io/fyne/v2/theme"
	"fyne.io/fyne/v2/widget"

	"biolstudio/internal/biolang"
)

type editorTab struct {
	path string
	edit *widget.Entry
}

type gui struct {
	win     fyne.Window
	tree    *widget.Tree
	tabs    *container.AppTabs
	out     *widget.Entry
	tpls         []string
	root    string
	mu      sync.Mutex
	editors map[string]*editorTab
}

func main() {
	a := app.NewWithID("studio.biol.biolstudio")
	w := a.NewWindow("Biol.Studio — BBB IDE (Go)")
	w.Resize(fyne.NewSize(1200, 780))

	g := &gui{
		win:     w,
		editors: map[string]*editorTab{},
	}

	// ---- 左侧：项目树 ----
	g.tree = widget.NewTree(
		func(id widget.TreeNodeID) []widget.TreeNodeID {
			if id == "" {
				if g.root == "" {
					return nil
				}
				return []widget.TreeNodeID{filepath.Base(g.root)}
			}
			path := g.nodePath(id)
			if path == "" {
				return nil
			}
			if st, err := os.Stat(path); err == nil && st.IsDir() {
				entries, _ := os.ReadDir(path)
				var kids []widget.TreeNodeID
				for _, e := range entries {
					if e.IsDir() || strings.HasSuffix(e.Name(), ".bio") || strings.HasSuffix(e.Name(), ".bl") || e.Name() == "package.toml" {
						kids = append(kids, filepath.Join(id, e.Name()))
					}
				}
				sort.Slice(kids, func(i, j int) bool { return kids[i] < kids[j] })
				return kids
			}
			return nil
		},
		func(id widget.TreeNodeID) bool {
			if id == "" {
				return g.root != ""
			}
			path := g.nodePath(id)
			if st, err := os.Stat(path); err == nil {
				return st.IsDir()
			}
			return false
		},
		func(branch bool) fyne.CanvasObject {
			return widget.NewLabel("")
		},
		func(id widget.TreeNodeID, branch bool, obj fyne.CanvasObject) {
			obj.(*widget.Label).SetText(id)
		},
	)
	g.tree.OnSelected = func(id widget.TreeNodeID) {
		if id == "" {
			return
		}
		path := g.nodePath(id)
		if st, err := os.Stat(path); err == nil && !st.IsDir() {
			g.openFile(path)
		}
	}

	// ---- 中间：编辑器标签 ----
	g.tabs = container.NewAppTabs()
	g.tabs.SetTabLocation(container.TabLocationTop)

	// ---- 底部：输出面板 ----
	g.out = widget.NewMultiLineEntry()
	g.out.Disable()
	g.out.SetPlaceHolder("run/build output")

	// ---- 布局 ----
	left := container.NewBorder(
		widget.NewLabelWithStyle("项目", fyne.TextAlignLeading, fyne.TextStyle{Bold: true}),
		nil, nil, nil, g.tree)
	midContent := container.NewBorder(nil, g.out, nil, nil, g.tabs)

	all := container.NewHSplit(left, midContent)
	all.SetOffset(0.25)

	// ---- 工具栏 ----
	tb := widget.NewToolbar(
		widget.NewToolbarAction(theme.FolderOpenIcon(), g.openProjectDialog),
		widget.NewToolbarAction(theme.DocumentCreateIcon(), g.newProjectDialog),
		widget.NewToolbarSeparator(),
		widget.NewToolbarAction(theme.MediaPlayIcon(), func() { g.runProject() }),
		widget.NewToolbarAction(theme.ConfirmIcon(), func() { g.buildProject() }),
		widget.NewToolbarAction(theme.SearchIcon(), func() { g.checkProject() }),
		widget.NewToolbarSeparator(),
		widget.NewToolbarAction(theme.ComputerIcon(), g.aboutDialog),
	)

	g.win.SetContent(container.NewBorder(tb, nil, nil, nil, all))
	g.win.Show()

	go g.loadTemplates()
	a.Run()
}

func (g *gui) nodePath(id widget.TreeNodeID) string {
	if g.root == "" {
		return ""
	}
	return filepath.Join(g.root, id)
}

func (g *gui) appendOut(s string) {
	g.mu.Lock()
	defer g.mu.Unlock()
	if g.out != nil {
		text := g.out.Text + s
		fyne.Do(func() { g.out.SetText(text) })
	}
}

func (g *gui) loadTemplates() {
	ts, err := biolang.ListTemplates()
	if err == nil {
		g.tpls = ts
	}
}

func (g *gui) openFile(path string) {
	g.mu.Lock()
	for _, t := range g.tabs.Items {
		if et, ok := g.editors[path]; ok && et.edit == t.Content {
			g.mu.Unlock()
			g.tabs.Select(t)
			return
		}
	}
	g.mu.Unlock()
	data, err := os.ReadFile(path)
	if err != nil {
		return
	}
	ed := widget.NewMultiLineEntry()
	ed.SetText(string(data))
	tab := &editorTab{path: path, edit: ed}
	g.mu.Lock()
	g.editors[path] = tab
	g.mu.Unlock()
	ti := container.NewTabItem(filepath.Base(path), ed)
	g.tabs.Append(ti)
	g.tabs.Select(ti)
}

func (g *gui) openProjectDialog() {
	d := dialog.NewFolderOpen(func(lu fyne.ListableURI, err error) {
		if err != nil || lu == nil {
			return
		}
		g.openProject(lu.Path())
	}, g.win)
	d.Show()
}

func (g *gui) openProject(root string) {
	g.root = root
	g.tree.Refresh()
	g.win.SetTitle(fmt.Sprintf("Biol.Studio — %s", filepath.Base(root)))
	mainFile := filepath.Join(root, "src", "main.bio")
	if _, err := os.Stat(mainFile); err == nil {
		g.openFile(mainFile)
	}
	g.checkProject()
}

func (g *gui) newProjectDialog() {
	name := widget.NewEntry()
	name.SetPlaceHolder("myapp")
	tpl := widget.NewSelect(g.tpls, nil)
	if len(g.tpls) > 0 {
		tpl.SetSelected(g.tpls[0])
	}
	base := widget.NewEntry()
	base.SetText(homeDir())
	form := dialog.NewForm("新建 BBB 项目", "创建", "取消",
		[]*widget.FormItem{
			widget.NewFormItem("项目名", name),
			widget.NewFormItem("模板", tpl),
			widget.NewFormItem("创建目录", base),
		},
		func(ok bool) {
			if !ok || name.Text == "" {
				return
			}
			res, err := biolang.ScaffoldProject(name.Text, tpl.Selected, base.Text)
			if err != nil {
				dialog.ShowError(err, g.win)
				return
			}
			g.appendOut(fmt.Sprintf("created project %s (template %s):\n", res.Name, res.Template))
			for _, f := range res.Files {
				g.appendOut("  " + f + "\n")
			}
			g.openProject(filepath.Join(base.Text, res.Name))
		}, g.win)
	form.Resize(fyne.NewSize(420, 0))
	form.Show()
}

func (g *gui) runProject() {
	if g.root == "" {
		dialog.ShowInformation("运行", "请先打开/新建项目", g.win)
		return
	}
	g.out.SetText("")
	go func() {
		g.appendOut(fmt.Sprintf("$ bbb run %s\n", g.root))
		r := biolang.RunProject(g.root)
		g.appendOut(r.Output + fmt.Sprintf("[exit %d]\n", r.ExitCode))
	}()
}

func (g *gui) buildProject() {
	if g.root == "" {
		dialog.ShowInformation("构建", "请先打开/新建项目", g.win)
		return
	}
	g.out.SetText("")
	go func() {
		g.appendOut(fmt.Sprintf("$ bbb build %s\n", g.root))
		r := biolang.BuildProject(g.root)
		g.appendOut(r.Output + fmt.Sprintf("[exit %d]\n", r.ExitCode))
	}()
}

func (g *gui) checkProject() {
	if g.root == "" {
		return
	}
	go func() {
		diags, err := biolang.CheckProject(g.root)
		if err != nil {
			return
		}
		var sb strings.Builder
		for _, d := range diags {
			sb.WriteString(fmt.Sprintf("%s:%d:%d: %s: %s\n", filepath.Base(d.File), d.Line, d.Col, d.Severity, d.Message))
		}
		if sb.Len() == 0 {
			sb.WriteString("check ok: no errors\n")
		}
		g.appendOut(sb.String())
	}()
}

func (g *gui) aboutDialog() {
	dialog.ShowInformation("Biol.Studio", "BBB IDE — Go 渲染层\n业务层: Python 功能层 + Rust bbb CLI", g.win)
}

func homeDir() string {
	h, _ := os.UserHomeDir()
	return h
}
