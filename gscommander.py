import sublime
import sublime_plugin
import gscommon as gs
import gsshell
import os
import re

DOMAIN = "GsCommander"
AC_OPTS = sublime.INHIBIT_WORD_COMPLETIONS | sublime.INHIBIT_EXPLICIT_COMPLETIONS
SPLIT_FN_POS_PAT = re.compile(r'(.+?)(?:[:](\d+))?(?:[:](\d+))?$')

try:
	stash
except:
	stash = {}

def active_wd(win=None):
	_, v = gs.win_view(win=win)
	return gs.basedir_or_cwd(v.file_name() if v else '')

def wdid(wd):
	return 'gscommander://%s' % wd

class EV(sublime_plugin.EventListener):
	def on_query_completions(self, view, prefix, locations):
			return []

class GsCommanderInitCommand(sublime_plugin.TextCommand):
	def run(self, edit, wd=None):
		v = self.view
		vs = v.settings()

		if not wd:
			wd = vs.get('gscommander.wd', active_wd(win=v.window()))

		was_empty = v.size() == 0
		s = '[  %s ]\n# \n' % wd

		if was_empty:
			v.insert(edit, v.size(), s)
		else:
			v.insert(edit, v.size(), '\n'+s)

		v.sel().clear()
		n = v.size()-1
		v.sel().add(sublime.Region(n, n))
		vs.set("gscommander.wd", wd)
		vs.set("rulers", [])
		vs.set("fold_buttons", True)
		vs.set("fade_fold_buttons", False)
		vs.set("gutter", True)
		vs.set("margin", 0)
		vs.set("tab_size", 2)
		vs.set("word_wrap", True)
		vs.set("indent_subsequent_lines", True)
		vs.set("line_numbers", False)
		vs.set("highlight_line", True)
		vs.set("draw_indent_guides", True)
		vs.set("indent_guide_options", ["draw_normal", "draw_active"])
		v.set_syntax_file('Packages/GoSublime/GsCommander.tmLanguage')

		if not was_empty:
			v.show(v.size()-1)

class GsCommanderOpenCommand(sublime_plugin.WindowCommand):
	def run(self, wd=None):
		win = self.window
		wid = win.id()
		if not wd:
			wd = active_wd(win=win)

		id = wdid(wd)
		st = stash.setdefault(wid, {})
		v = st.get(id)
		if v is None:
			v = win.get_output_panel(id)
			st[id] = v

		win.run_command("show_panel", {"panel": ("output.%s" % id)})
		win.focus_view(v)
		v.run_command('gs_commander_init', {'wd': wd})

class GsCommanderOpenSelectionCommand(sublime_plugin.TextCommand):
	def is_enabled(self):
		pos = self.view.sel()[0].begin()
		return self.view.score_selector(pos, 'path.gscommander') > 0

	def run(self, edit):
		v = self.view
		pos = v.sel()[0].begin()
		wd = v.settings().get('gscommander.wd') or active_wd()
		fn = v.substr(v.extract_scope(pos))
		m = SPLIT_FN_POS_PAT.match(fn)
		print m, gs.apath((m.group(1) if m else fn), wd), m.group(1)
		fn = gs.apath((m.group(1) if m else fn), wd)
		row = max(0, int(m.group(2))-1 if (m and m.group(2)) else 0)
		col = max(0, int(m.group(3))-1 if (m and m.group(3)) else 0)

		if os.path.exists(fn):
			gs.focus(fn, row, col, win=self.view.window())
		else:
			gs.notice(DOMAIN, "Invalid path `%s'" % fn)

class GsCommanderExecCommand(sublime_plugin.TextCommand):
	def is_enabled(self):
		pos = self.view.sel()[0].begin()
		return self.view.score_selector(pos, 'text.gscommander') > 0

	def run(self, edit):
		v = self.view
		pos = v.sel()[0].begin()
		line = v.line(pos)
		cmd = v.substr(line).lstrip()
		if cmd.startswith('#'):
			cmd = cmd.strip('# ')
			if not cmd:
				v.run_command('gs_commander_init')
				return

			f = globals().get('cmd_%s' % cmd)
			if f:
				f(v, edit)
				return

			wd = v.settings().get('gscommander.wd')
			v.replace(edit, line, ('[ %s ]' % cmd))
			c = gsshell.ViewCommand(cmd=cmd, shell=True, view=v, cwd=wd)

			def on_output_done(c):
				def cb():
					win = sublime.active_window()
					if win is not None:
						win.run_command("gs_commander_open")
				sublime.set_timeout(cb, 0)

			oo = c.on_output
			def on_output(c, ln):
				oo(c, '\t'+ln)

			c.on_output = on_output
			c.output_done.append(on_output_done)
			c.start()
		else:
			v.insert(edit, v.sel()[0].begin(), '\n')

def cmd_reset(view, edit):
	view.erase(edit, sublime.Region(0, view.size()))
	view.run_command('gs_commander_init')

def cmd_clear(view, edit):
	cmd_reset(view, edit)