import html
import socket
import ssl
import time
import tkinter.font
import urllib
import urllib.parse
from html.parser import HTMLParser
import pygments as py
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import HtmlLexer, CssLexer
from tkinter import *
from tkinter import ttk
from tkinter.constants import FALSE, TRUE, END

import dukpy

WIDTH, HEIGHT = 800, 600
HSTEP, VSTEP = 13, 18
SCROLL_STEP = 100
TEXTSIZE = 16
FONTS = {}
CHROME_PX = 100
BOOKMARKS = []
INPUT_WIDTH_PX = 200
EVENT_DISPATCH_CODE = "new Node(dukpy.handle).dispatchEvent(new Event(dukpy.type))"
COOKIE_JAR = {}
REQUEST_LIST = []


def test_parse(text):
    parser = HTMLParser(text)
    print_tree(parser.parse())


def get_host(url):
    _, parsed_url = url.split("://", 1)
    host, _ = parsed_url.split("/", 1)
    if ":" in host:
        host, _ = host.split(":", 1)
    return host


class MyHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.nodes = []
        self.stack = []
        self.text = ""
        self.script = False
        self.style = False
        self.script_text = ""
        self.style_text = ""

    def handle_starttag(self, tag, attrs):
        if tag == "script":
            self.script = True
        elif tag == "style":
            self.style = True
        self.stack.append((tag, attrs))

    def handle_endtag(self, tag):
        if tag == "script":
            self.script = False
            self.nodes.append(Text(self.script_text, self.stack[-1][0]))
            self.script_text = ""
        elif tag == "style":
            self.style = False
            self.nodes.append(Text(self.style_text, self.stack[-1][0]))
            self.style_text = ""
        else:
            if self.text:
                self.nodes.append(Text(self.text, self.stack[-1][0]))
                self.text = ""
            self.nodes.append(
                Element(tag, dict(self.stack.pop()[1]), self.stack[-1][0])
            )

    def handle_data(self, data):
        if self.script:
            self.script_text += data
        elif self.style:
            self.style_text += data
        else:
            self.text += data

    def feed(self, data):
        super().feed(data)
        return self.nodes


class Tab:
    def __init__(self, browser):
        self.browser = browser
        with open("browser.css") as f:
            self.default_style_sheet = CSSParser(f.read()).parse()
        self.history = []
        self.scroll = 0
        self.focus = None
        self.nodes = None
        self.rules = []
        self.url = None
        self.host = None
        self.previous = (None, None)

    def allowed_request(self, url):
        return self.allowed_origins == None or url_origin(url) in self.allowed_origins

    def click(self, xx, yy, is_middle=False):
        x, y = xx, yy
        y += self.scroll
        objs = [
            obj
            for obj in tree_to_list(self.document, [])
            if obj.x <= x < obj.x + obj.width and obj.y <= y < obj.y + obj.height
        ]
        if not objs:
            return
        elt = objs[-1].node
        while elt:
            if isinstance(elt, Text):
                pass
            elif elt.tag == "input":
                if self.js.dispatch_event("click", elt):
                    return
                if elt.attributes.get("type", "") == "checkbox":
                    if "checked" in elt.attributes:
                        del elt.attributes["checked"]
                    else:
                        elt.attributes["checked"] = "anythingpavelsays"
                else:
                    elt.attributes["value"] = ""
                    self.focus = elt
                self.render()
                return
            elif elt.tag == "button":
                if self.js.dispatch_event("click", elt):
                    return
                while elt:
                    if elt.tag == "form" and "action" in elt.attributes:
                        return self.submit_form(elt)
                    elt = elt.parent
            elif elt.tag == "a" and "href" in elt.attributes:
                if self.js.dispatch_event("click", elt):
                    return
                url = resolve_url(elt.attributes["href"], self.url)
                if not is_middle:
                    if elt.attributes["href"].startswith("#"):
                        self.fragment = elt.attributes["href"][1:]
                        if "#" in self.url:
                            self.url = self.url.split(
                                "#")[0] + elt.attributes["href"]
                        else:
                            self.url += elt.attributes["href"]
                        for object in tree_to_list(self.document, []):
                            if (
                                isinstance(object.node, Element)
                                and object.node.attributes.get("id") == self.fragment
                            ):
                                self.scroll = object.y
                    else:
                        self.scroll = 0
                        return self.load(url)
                else:
                    return url
            elif elt.tag == "form" and "action" in elt.attributes:
                return self.submit_form(elt)
            elt = elt.parent

    def render(self):
        style(self.nodes, sorted(self.rules, key=cascade_priority))
        self.document = DocumentLayout(self.nodes)
        self.document.layout()
        self.display_list = []
        self.document.paint(self.display_list)

    def submit_form(self, elt):
        if self.js.dispatch_event("submit", elt):
            return
        inputs = [
            node
            for node in tree_to_list(elt, [])
            if isinstance(node, Element)
            and node.tag == "input"
            and "name" in node.attributes
        ]
        body = ""
        for input in inputs:
            defaultValue = ""
            if input.attributes.get("type", "").lower() == "checkbox":
                if "checked" not in input.attributes:
                    continue
                else:
                    defaultValue = input.attributes.get("value", "on")
            name = input.attributes["name"]
            value = input.attributes.get("value", defaultValue)
            name = urllib.parse.quote(name)
            value = urllib.parse.quote(value)
            body += "&" + name + "=" + value
        body = body[1:]
        url = resolve_url(elt.attributes["action"], self.url)

        methodtype = elt.attributes.get("method", "get")
        if methodtype.lower() != "post":
            url += "?" + body
            body = None

        self.load(url, body)

    def go_back(self):
        if len(self.history) > 1:
            self.history.pop()
            back = self.history.pop()
            self.load(back)

    def load(self, url, body=None):
        self.focus = None

        if url == "about:bookmarks":
            body = ""
            for url in BOOKMARKS:
                body += f'<a href="{url}">{url}</a>'
            self.nodes = HTMLParser(body).parse()
            self.document = DocumentLayout(self.nodes)
            self.document.layout()
            self.display_list = []
            self.document.paint(self.display_list)
        else:
            REQUEST_LIST.clear()
            self.allowed_origins = None
            self.history.append(url)
            self.url = url
            self.host = get_host(url)

            refererHeader = self.setreferer(url)
            self.headers, body = request(
                url, self.url, headers=refererHeader, payload=body
            )
            self.storereferer(self.headers, url)
            self.nodes = HTMLParser(body).parse()
            if "content-security-policy" in self.headers:
                csp = self.headers["content-security-policy"].split()
                if len(csp) > 0 and csp[0] == "default-src":
                    self.allowed_origins = csp[1:]
            # find all JS scripts
            scripts = [
                node.attributes["src"]
                for node in tree_to_list(self.nodes, [])
                if isinstance(node, Element)
                and node.tag == "script"
                and "src" in node.attributes
            ]
            self.js = JSContext(self)
            for script in scripts:
                try:
                    script_url = resolve_url(script, url)
                    if not self.allowed_request(script_url):
                        self.js.warning(f"Blocked script: {script} due to CSP")
                        continue
                    refererHeader = self.setreferer(script_url)
                    header, body = request(
                        script_url, url, headers=refererHeader)
                    self.storereferer(header, url)
                    self.js.run(body)
                except dukpy.JSRuntimeError as e:
                    self.js.error(f"Error running script: {script}\n\t{e}")
            links = [
                node.attributes["href"]
                for node in tree_to_list(self.nodes, [])
                if isinstance(node, Element)
                and node.tag == "link"
                and "href" in node.attributes
                and node.attributes.get("rel") == "stylesheet"
            ]
            for link in links:
                try:
                    link_url = resolve_url(link, url)
                    # if not self.allowed_request(link_url):
                    #     print("Blocked style", link, "due to CSP")
                    #     continue
                    refererHeader = self.setreferer(link_url)
                    header, body = request(
                        link_url, url, headers=refererHeader)
                    self.storereferer(header, url)
                except:
                    continue
                self.rules.extend(CSSParser(body).parse())
            self.rules = self.default_style_sheet.copy()
            style(self.nodes, sorted(self.rules, key=cascade_priority))

            if "#" in url:
                self.fragment = url.split("#")[1]
                for object in tree_to_list(self.document, []):
                    if (
                        isinstance(object.node, Element)
                        and object.node.attributes.get("id") == self.fragment
                    ):
                        self.scroll = object.y

            if self.browser.requestList is not None:
                self.browser.requestList.delete(0, tkinter.END)
                for i, rq in enumerate(REQUEST_LIST):
                    self.browser.requestList.insert(i, rq)

            self.render()

    def setreferer(self, url):
        headers = {}
        referrer, policy = self.previous
        if referrer is not None:
            if policy == "no-referrer":
                headers.clear()
            elif policy == "same-origin":
                if get_host(url) == get_host(referrer):
                    headers["referer"] = referrer
            else:
                headers["referer"] = referrer
        else:
            headers["referer"] = url
        return headers

    def storereferer(self, headers, url):
        if "referrer-policy" in headers:
            ref = headers["referrer-policy"]
            self.previous = (url, ref)

    def keypress(self, char):
        if self.focus:
            if self.js.dispatch_event("keydown", self.focus):
                return
            self.focus.attributes["value"] += char
            self.render()

    def tab(self):
        inputs = [
            obj.node
            for obj in tree_to_list(self.document, [])
            if isinstance(obj.node, Element) and obj.node.tag == "input"
        ]
        if not self.focus:
            self.focus = inputs[0].node
        else:
            index = inputs.index(self.focus)
            self.focus = inputs[(index + 1) % len(inputs)]

        self.focus.attributes["value"] = ""
        self.render()

    def draw(self, canvas):
        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT - CHROME_PX:
                continue
            if cmd.bottom < self.scroll:
                continue
            cmd.execute(self.scroll - CHROME_PX, canvas)
            if self.focus:
                obj = [
                    obj
                    for obj in tree_to_list(self.document, [])
                    if obj.node == self.focus
                ][0]
                text = self.focus.attributes.get("value", "")
                x = obj.x + obj.font.measure(text)
                y = obj.y - self.scroll + CHROME_PX
                canvas.create_line(x, y, x, y + obj.height)

    def scrolldown(self):
        max_y = self.document.height - (HEIGHT - CHROME_PX)
        self.scroll = min(self.scroll + SCROLL_STEP, max_y)

    def scrollup(self):
        max_y = self.document.height - (HEIGHT - CHROME_PX)
        self.scroll = max(self.scroll - SCROLL_STEP, 0)

    # enterkey

    def enterkey(self):
        if self.focus:
            elt = self.focus
            while elt:
                if elt.tag == "form" and "action" in elt.attributes:
                    return self.submit_form(elt)
                elt = elt.parent

    def __repr__(self):
        s = "Tab(history=['"
        for x in range(len(self.history)):
            s += "{}".format(self.history[x])
            if x == len(self.history) - 1:
                break
            s += "', '"
        s += "'])"
        return s


class Browser:
    def __init__(self):
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=WIDTH, height=HEIGHT)
        self.canvas.pack(fill="both", expand=TRUE)
        self.window.bind("<Down>", self.handle_down)
        self.window.bind("<Up>", self.handle_up)
        self.scroll = 0
        self.window.bind("<Button-1>", self.handle_click)
        self.window.bind("<Key>", self.handle_key)
        self.window.bind("<Return>", self.handle_enter)
        self.window.bind("<BackSpace>", self.handle_backspace)
        self.window.bind("<Button-2>", self.handle_middle_click)
        self.window.bind("<Tab>", self.handle_tab)
        self.window.bind("<MouseWheel>", self.handle_scroll)
        self.url = None
        self.tabs = []
        self.active_tab = None
        self.focus = None
        self.address_bar = ""
        self.input = []
        self.requestList = None

    def drawDevTools(self):

        self.devToolsWindow = Toplevel(self.window)
        self.devToolsWindow.resizable(0, 0)
        self.windowwidth, self.windowheight = self.computeScreenDimensions()
        self.openingWindowWidth = int(self.windowwidth * 0.5)
        self.openingWindowHeight = int(self.windowheight * 0.7)
        self.devToolsWindow.geometry(
            str(self.openingWindowWidth) + "x" + str(self.openingWindowHeight)
        )
        self.devToolsWindow.title("Developer Tools")
        self.devToolsTabs = ttk.Notebook(self.devToolsWindow)
        self.devToolsHtmlTab = ttk.Frame(self.devToolsTabs)
        self.devToolsConsoleTab = ttk.Frame(self.devToolsTabs)
        self.devToolsNetworkTab = ttk.Frame(self.devToolsTabs)
        self.devToolsTabs.add(self.devToolsHtmlTab, text="HTML")
        self.devToolsTabs.add(self.devToolsConsoleTab, text="Console")
        self.devToolsTabs.add(self.devToolsNetworkTab, text="Network")

        self.drawDevToolHtmlTree()
        self.drawDevToolStyleTree()
        self.drawDevToolsNetworkTrace()
        self.drawDevToolsConsole()

    def drawDevToolHtmlTree(self):

        headers, body = request(
            self.tabs[self.active_tab].url, self.tabs[self.active_tab].url
        )
        htmlTree = []
        self.w = tkinter.Text(
            self.devToolsHtmlTab,
            wrap=WORD,
            selectborderwidth=3,
            padx=5,
            height=self.openingWindowHeight - 498,
            relief="ridge",
            font=("JetBrains Mono", 10),
        )

        for tag, val in HtmlFormatter().style:
            if val["color"] is not None and val["bold"] is False:
                self.w.tag_configure(
                    str(tag), foreground="#{}".format(val["color"]))
            if val["color"] is not None and val["bold"] is True:
                self.w.tag_configure(
                    str(tag),
                    foreground="#{}".format(val["color"]),
                    font=("JetBrains Mono", 10),
                )
            if val["bold"] is True:
                self.w.tag_configure(str(tag), font=(
                    "JetBrains Mono", 10, "bold"))

        for token, content in py.lex(body, HtmlLexer()):
            self.w.insert(END, content, str(token))
        self.myscroll = ttk.Scrollbar(
            self.devToolsHtmlTab, orient="vertical", command=self.w.yview
        )
        self.myscroll.grid(row=0, column=2, sticky="NE")
        self.w.grid_columnconfigure(2, weight=1)
        self.w["yscrollcommand"] = self.myscroll.set
        self.w.grid(column=0, row=0, columnspan=2, sticky="NW")

    def computeScreenDimensions(self):
        x = self.devToolsWindow.winfo_screenwidth()
        y = self.devToolsWindow.winfo_screenheight()
        return x, y

    def drawDevToolStyleTree(self):
        with open("browser.css") as f:
            self.style_sheet = f.read()
        style_tree = DevToolsCSSParser(self.style_sheet).parse()
        self.l = "/* CSS Style Sheet*/\n\n"
        for x in style_tree:
            self.l += str(x)
        self.y = tkinter.Text(
            self.devToolsHtmlTab,
            wrap=WORD,
            selectborderwidth=3,
            padx=5,
            height=self.openingWindowHeight - 498,
            relief="ridge",
            font=("JetBrains Mono", 9),
        )
        for token, content in py.lex(self.l, CssLexer()):
            self.y.insert(END, content, str(token))
        for tag, val in HtmlFormatter().style:

            if val["color"] is not None and val["bold"] is False:
                self.y.tag_configure(
                    str(tag), foreground="#{}".format(val["color"]))
            if val["color"] is not None and val["bold"] is True:
                self.y.tag_configure(
                    str(tag),
                    foreground="#{}".format(val["color"]),
                    font=("JetBrains Mono", 10, "bold"),
                )
            if val["bold"] is True:
                self.y.tag_configure(str(tag), font=(
                    "JetBrains Mono", 10, "bold"))

        self.myscroll2 = ttk.Scrollbar(
            self.devToolsHtmlTab, orient="vertical", command=self.y.yview
        )
        self.myscroll2.grid(row=0, column=3, sticky="NE")
        self.y.grid_columnconfigure(2, weight=1)
        self.y["yscrollcommand"] = self.myscroll2.set
        self.y.grid(column=3, row=0, ipady=10, sticky="NE")

    def drawDevToolsNetworkTrace(self):
        self.requestList = Listbox(
            self.devToolsNetworkTab, width=75, height=30)
        for i, rq in enumerate(REQUEST_LIST):
            self.requestList.insert(i, rq)
        self.requestList.pack()

    def drawDevToolsConsole(self):
        self.text = tkinter.Text(self.devToolsConsoleTab)
        self.text.tag_configure("prompt", foreground="#000080", font=("bold"))
        self.text.tag_configure("error", foreground="#e40000")
        self.text.tag_configure("warning", foreground="#ffc107")
        self.text.tag_configure("input", foreground="#0d6efd")
        self.text.tag_configure("output", foreground="#717171")
        self.console_output()

        self.text.configure(state="disabled", font=("JetBrains Mono", 10))
        self.text.bind("<Button-2>", self.do_popup, add="+")
        self.text.pack(fill="both", expand=True)

        self.entry = Entry(self.devToolsConsoleTab)
        self.entry.config(font=("JetBrains Mono", 10))
        self.entry.bind("<Return>", self.console_input, add="+")
        self.entry.focus_force()
        self.entry.pack(fill=X)

        self.menu = Menu(self.devToolsConsoleTab, tearoff=0)
        self.menu.add_command(label="Clear", command=self.clear_console)

        self.devToolsTabs.pack(expand=1, fill="both")

    def console_output(self):
        tab = self.tabs[self.active_tab]
        for message in tab.messages:
            self.console_prompt("\n<<  ")
            output = f"{message['text']}"
            self.text.insert(END, output)
            if message["level"] == "error":
                self.text.tag_add("error", f"end - {len(output)+1}c", "end-1c")

            if message["level"] == "warning":
                self.text.tag_add(
                    "warning", f"end - {len(output)+1}c", "end-1c")

        tab.messages = []

    def console_input(self, e):
        result = self.entry.get()
        self.text.configure(state="normal")
        if len(result) > 0:
            tab = self.tabs[self.active_tab]
            self.console_prompt("\n>>  ")
            self.text.insert(END, f"{result}")
            self.text.tag_add("input", f"end - {len(result) + 1}c", "end-1c")

            try:
                # tab.js.log(str(tab.js.run(result)))
                r = tab.js.run(result)
                if r is not None:
                    tab.js.log(str(r))

            except dukpy.JSRuntimeError as e:
                tab.js.error(str(e))
        else:
            self.console_prompt("\n->  ")
        self.console_output()
        self.text.configure(state="disabled")
        self.entry.delete(0, "end")

    def console_prompt(self, prompt):
        self.text.insert(END, prompt)
        self.text.tag_add("prompt", "end-5c", "end-3c")

    def do_popup(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def clear_console(self):
        self.text.configure(state="normal")
        self.text.delete("1.0", END)
        self.text.configure(state="disabled")

    def draw(self):
        self.canvas.delete("all")
        self.tabs[self.active_tab].draw(self.canvas)
        self.canvas.create_rectangle(0, 0, WIDTH, CHROME_PX, fill="#1A2126")
        tabfont = get_font(20, "normal", "roman")
        for i, tab in enumerate(self.tabs):
            name = "Tab {}".format(i + 1)
            x1, x2 = 40 + 80 * i, 120 + 80 * i
            self.canvas.create_line(x1, 0, x1, 40)
            self.canvas.create_line(x2, 0, x2, 40)
            self.canvas.create_text(
                x1 + 40, 20, anchor="center", text=name, font=tabfont
            )
            if i == self.active_tab:
                self.canvas.create_line(0, 40, x1, 40)
                self.canvas.create_line(x2, 40, WIDTH, 40)
        buttonfont = get_font(20, "normal", "roman")
        self.canvas.create_rectangle(10, 10, 30, 30, width=1, fill="#1A2126")
        self.canvas.create_text(
            14, 8, anchor="nw", text="\N{plus sign}", font=buttonfont
        )
        self.canvas.create_rectangle(40, 50, WIDTH - 50, 90, width=1)
        url = self.tabs[self.active_tab].url
        # self.canvas.create_text(85, 57, anchor='nw', text=url, font=buttonfont)
        # w = buttonfont.measure(url)
        # self.canvas.create_line(85 + w, 55, 85 + w, 85)
        self.canvas.create_rectangle(10, 50, 35, 90, width=1)
        self.canvas.create_polygon(15, 70, 30, 55, 30, 85, fill="#f4f4f4")
        if (
            self.tabs[self.active_tab].url.startswith("https")
            and "x-magicheader" not in self.tabs[self.active_tab].headers
        ):
            self.canvas.create_text(
                55, 57, anchor="nw", text="\N{lock}", font=buttonfont
            )

        if self.focus == "address bar":
            self.canvas.create_rectangle(
                40, 50, WIDTH - 50, 90, fill="#1A2126", width=1
            )

            self.canvas.create_text(
                85, 57, anchor="nw", text=self.address_bar, font=buttonfont
            )
            w = buttonfont.measure(self.address_bar)
            self.canvas.create_line(85 + w, 60, 85 + w, 80)
        else:
            url = self.tabs[self.active_tab].url
            self.canvas.create_text(
                85, 58, anchor="nw", text=url, font=get_font(20, "normal", "roman")
            )

        if self.tabs[self.active_tab].url in BOOKMARKS:
            self.canvas.create_rectangle(
                WIDTH - 40, 50, WIDTH - 10, 90, width=1, fill="#1A2126"
            )
            self.canvas.create_text(
                WIDTH - 36,
                52,
                anchor="nw",
                text="\N{Black diamond}",
                font=get_font(30, "normal", "roman"),
            )
        else:
            self.canvas.create_rectangle(
                WIDTH - 40, 50, WIDTH - 10, 90, width=1, fill="#1A2126"
            )
        # Dev Tools Button
        buttonfont = get_font(14, "normal", "roman")
        self.canvas.create_rectangle(WIDTH - 40, 10, WIDTH - 10, 30, width=1)
        self.canvas.create_text(
            WIDTH - 24,
            17,
            text="\N{hammer and pick}",
            font=get_font(30, "normal", "roman"),
        )

    def load(self, url):
        new_tab = Tab(self)
        new_tab.load(url)
        self.active_tab = len(self.tabs)
        self.tabs.append(new_tab)
        self.draw()

    def handle_backspace(self, e):
        if self.focus == "address bar":
            self.address_bar = self.address_bar[:-1]
            self.draw()

    def handle_enter(self, e):
        if self.focus == "address bar":
            self.tabs[self.active_tab].load(self.address_bar)
            self.focus = None
            self.draw()
        # enterkey
        if self.focus == "content":
            self.tabs[self.active_tab].enterkey()
            self.draw()

    def handle_tab(self, e):
        if self.focus == "content":
            self.tabs[self.active_tab].tab()
            self.draw()

    def handle_key(self, e):
        if len(e.char) == 0:
            return
        if not (0x20 <= ord(e.char) < 0x7F):
            return

        if self.focus == "address bar":
            self.address_bar += e.char
            self.draw()
        elif self.focus == "content":
            self.tabs[self.active_tab].keypress(e.char)
            self.draw()

    def handle_down(self, e):
        self.tabs[self.active_tab].scrolldown()
        self.draw()

    def handle_up(self, e):
        self.tabs[self.active_tab].scrollup()
        self.draw()

    def handle_middle_click(self, e):
        if e.y > CHROME_PX:
            url = self.tabs[self.active_tab].click(e.x, e.y - CHROME_PX, True)
            self.load_new_tab(url)

    def handle_scroll(self, e):
        if e.delta < 0:
            self.tabs[self.active_tab].scrolldown()
        else:
            self.tabs[self.active_tab].scrollup()
        self.draw()

    def load_new_tab(self, url):
        new_tab = Tab(self)
        new_tab.load(url)
        self.tabs.append(new_tab)
        self.draw()

    def handle_click(self, e):
        self.focus = None
        if e.y < CHROME_PX:
            self.focus = None
            if 40 <= e.x < 40 + 80 * len(self.tabs) and 0 <= e.y < 40:
                self.active_tab = int((e.x - 40) / 80)
            elif 10 <= e.x < 35 and 40 <= e.y < 90:
                self.tabs[self.active_tab].go_back()
            elif 10 <= e.x < 30 and 10 <= e.y < 30:
                self.load("https://browser.engineering/")
            elif 40 <= e.x < WIDTH - 50 and 40 <= e.y < 90:
                self.focus = "address bar"
                self.address_bar = ""
            elif WIDTH - 40 <= e.x < WIDTH - 10 and 50 <= e.y < 90:
                if self.tabs[self.active_tab].url not in BOOKMARKS:
                    BOOKMARKS.append(self.tabs[self.active_tab].url)
                else:
                    BOOKMARKS.remove(self.tabs[self.active_tab].url)
            elif WIDTH - 40 <= e.x < WIDTH - 10 and 10 <= e.y < 30:
                self.drawDevTools()
        else:
            self.focus = "content"
            self.tabs[self.active_tab].click(e.x, e.y - CHROME_PX)
        self.draw()


def get_font(size, weight, slant, family=None):
    if family is None:
        family = "Helvetica"
    key = (size, weight, slant, family)
    if key not in FONTS:
        font = tkinter.font.Font(
            size=size, weight=weight, slant=slant, family=family)
        FONTS[key] = font
    return FONTS[key]


class Text:
    def __init__(self, text, parent):
        self.text = text
        self.children = []
        self.parent = parent

    def __repr__(self):
        return repr(self.text)


class Element:
    def __init__(self, tag, attributes, parent):
        self.tag = tag
        self.attributes = attributes
        self.children = []
        self.parent = parent

    def __repr__(self):
        s = "<" + self.tag
        for key, val in self.attributes.items():
            s += " " + key + "=" + '"' + val + '"'
        s += ">"
        return s


class DevToolsHTMLParser:
    def __init__(self, body):
        self.body = body
        self.tree = []

    def parse(self):
        text = ""
        for c in self.body:
            text += c
        self.tree.append(text)
        return self.tree


class DevToolsCSSParser:
    def __init__(self, styles):
        self.style_list = styles
        self.tree = []

    def parse(self):
        text = ""
        for c in self.style_list:
            text += c
        self.tree.append(text)
        return self.tree


class HTMLParser:
    SELF_CLOSING_TAGS = [
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    ]
    HEAD_TAGS = [
        "base",
        "basefont",
        "bgsound",
        "noscript",
        "link",
        "meta",
        "title",
        "style",
        "script",
    ]

    def __init__(self, body):
        self.body = body
        self.unfinished = []

    def add_text(self, text):
        if text.isspace():
            return
        self.implicit_tags(None)
        parent = self.unfinished[-1]
        node = Text(text, parent)
        parent.children.append(node)

    def add_tag(self, tag):
        tag, attributes = self.get_attributes(tag)
        if tag.startswith("!"):
            return
        self.implicit_tags(tag)
        if tag.startswith("/"):
            if len(self.unfinished) == 1:
                return
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        elif tag.startswith("p"):
            temp = [node.tag for node in self.unfinished]
            nodes = []
            while "p" in temp:
                node = self.unfinished.pop()
                temp.pop()
                parent = self.unfinished[-1]
                parent.children.append(node)
                nodes.append(node)

            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

            for node in reversed(nodes[:-1]):
                parent = self.unfinished[-1]
                node = Element(node.tag, node.attributes, parent)
                self.unfinished.append(node)

        elif tag in self.SELF_CLOSING_TAGS:
            parent = self.unfinished[-1]
            node = Element(tag, attributes, parent)
            parent.children.append(node)
        else:
            parent = self.unfinished[-1] if self.unfinished else None
            node = Element(tag, attributes, parent)
            self.unfinished.append(node)

    def implicit_tags(self, tag):
        while True:
            open_tags = [node.tag for node in self.unfinished]
            if open_tags == [] and tag != "html":
                self.add_tag("html")
            elif open_tags == ["html"] and tag not in ["head", "body", "/html"]:
                if tag in self.HEAD_TAGS:
                    self.add_tag("head")
                else:
                    self.add_tag("body")
            elif (
                open_tags == ["html", "head"] and tag not in [
                    "/head"] + self.HEAD_TAGS
            ):
                self.add_tag("/head")
            else:
                break

    def get_attributes(self, text):
        parts = text.split()
        tag = parts[0].lower()
        attributes = {}
        for attrpair in parts[1:]:
            if "=" in attrpair:
                key, value = attrpair.split("=", 1)
                if len(value) > 2 and value[0] in ["'", '"']:
                    value = value[1:-1]
                attributes[key.lower()] = value
            else:
                attributes[attrpair.lower()] = ""
        return tag, attributes

    def finish(self):
        while len(self.unfinished) > 1:
            node = self.unfinished.pop()
            parent = self.unfinished[-1]
            parent.children.append(node)
        return self.unfinished.pop()

    def parse(self):
        text = ""
        in_style = False
        in_tag = False
        in_comment = False
        in_script = False
        for c in self.body:
            if in_tag and text.startswith("!--"):
                in_comment = True
            if in_tag and text == "script":
                in_script = True
            if in_tag and text == "style":
                in_style = True

            if c == "<" and in_script and not in_tag:

                text += c
                continue
            elif c == ">" and in_script and not in_tag and not text.endswith("/script"):
                text += c
                continue
            elif c == "<" and in_style and not in_tag and not text.endswith("/style"):
                text += c
                continue
            elif c == "<" and not in_comment:
                in_tag = True
                if text:
                    self.add_text(text)
                text = ""
                continue
            elif c == ">":
                if in_comment and text[3:].endswith("--"):
                    in_comment = False
                elif in_script and text.endswith("</script"):
                    if text:
                        print(text[:-8])
                    in_script = False
                elif in_style and text.endswith("</style"):
                    if text:
                        print(text[:-7])
                    in_style = False
                elif not in_comment and in_tag:
                    self.add_tag(text)
                else:
                    text += c
                    continue
                in_tag = False
                text = ""
            else:
                text += c
        if not in_tag and text:
            self.add_text(text)
        return self.finish()


def print_tree(node, indent=0):
    print(" " * indent, node)
    for child in node.children or []:
        print_tree(child, indent + 2)


BLOCK_ELEMENTS = [
    "html",
    "body",
    "article",
    "section",
    "nav",
    "aside",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hgroup",
    "header",
    "footer",
    "address",
    "p",
    "hr",
    "pre",
    "blockquote",
    "ol",
    "ul",
    "menu",
    "li",
    "dl",
    "dt",
    "dd",
    "figure",
    "figcaption",
    "main",
    "div",
    "table",
    "form",
    "fieldset",
    "legend",
    "details",
    "summary",
]


def layout_mode(node):
    if isinstance(node, Text):
        return "inline"
    elif node.children:
        for child in node.children:
            if isinstance(child, Text):
                continue
            if child.tag in BLOCK_ELEMENTS:
                return "block"
        return "inline"
    else:
        return "block"


class DrawText:
    def __init__(self, x1, y1, text, font, color, anchor="None"):
        if anchor == "None":
            anchor = "nw"

        self.top = y1
        self.left = x1
        self.text = html.unescape(text)
        self.font = font
        self.bottom = y1 + font.metrics("linespace")
        self.color = (color,)
        self.anchor = anchor

    def execute(self, scroll, canvas):
        # print(self.text, self.font, self.color)
        canvas.create_text(
            self.left,
            self.top - scroll,
            text=self.text,
            anchor=self.anchor,
            fill=self.color,
            font=self.font,
        )

    def __repr__(self):
        return f"DrawText(top={str(self.top)} left={str(self.left)} bottom={str(self.bottom)} text={self.text} font={str(self.font)})"


class DrawRect:
    def __init__(self, x1, y1, x2, y2, color):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll, canvas):
        canvas.create_rectangle(
            self.left,
            self.top - scroll,
            self.right,
            self.bottom - scroll,
            width=0,
            fill=self.color,
        )

    def __repr__(self):
        s = "DrawRect"
        s += (
            "(top="
            + str(self.top)
            + " left="
            + str(self.left)
            + " bottom="
            + str(self.bottom)
            + " right="
            + str(self.right)
            + " color="
            + self.color
            + ")"
        )
        return s


class TagSelector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 1

    def matches(self, node):
        return isinstance(node, Element) and self.tag == node.tag

    def __repr__(self):
        s = "TagSelector(tag=" + self.tag + ", priority=" + \
            str(self.priority) + ")"
        return s


class DescendantSelector:
    def __init__(self, ancestor, descendant):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    def matches(self, node):
        if not self.descendant.matches(node):
            return False
        while node.parent:
            if self.ancestor.matches(node.parent):
                return True
            node = node.parent
        return False

    def __repr__(self):
        s = (
            "DescendantSelector(ancestor="
            + str(self.ancestor)
            + ", descendant="
            + str(self.descendant)
            + ", priority="
            + str(self.priority)
            + ")"
        )
        return s


class ClassSelector:
    def __init__(self, tag):
        self.tag = tag
        self.priority = 10

    def matches(self, node):
        if isinstance(node, Element) and "class" in node.attributes:
            if self.tag in node.attributes["class"].split():
                return True
            else:
                return False
        else:
            return False

    def __repr__(self):
        return f"ClassSelector(html_class={str(self.tag)}, priority={self.priority})"


class CSSParser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def whitespace(self):
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self):
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
                self.i += 1
            else:
                break
        assert self.i > start
        return self.s[start: self.i]

    def literal(self, literal):
        assert self.i < len(self.s) and self.s[self.i] == literal
        self.i += 1

    def pair(self):
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.lower(), val

    def body(self):
        pairs = {}
        properties = self.s.split()
        index = -1

        if "font:" in properties:
            index = properties.index("font:")

        if index != -1 and properties[index + 1][-1:] != ";":
            temp = ""
            if index != 0:
                temp += " ".join(str(s) for s in properties[:index]) + " "
            temp += "font-style: " + str(properties[index + 1]) + "; "
            temp += "font-weight: " + str(properties[index + 2]) + "; "
            temp += "font-size: " + str(properties[index + 3]) + "; "
            temp += "font-family: " + str(properties[index + 4]) + " "
            temp += " ".join(str(s) for s in properties[index + 5:])
            self.s = temp

        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair()
                pairs[prop.lower()] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except AssertionError:
                why = self.ignore_until([";", "}"])
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def ignore_until(self, chars):
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1

    def selector(self):
        current = self.word().lower()
        if "." in current:
            out = ClassSelector(current.strip("."))
        else:
            out = TagSelector(current)
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            tag = self.word().lower()
            if "." in tag:
                descendant = ClassSelector(tag.strip("."))
            else:
                descendant = TagSelector(tag.lower())
            out = DescendantSelector(out, descendant)
            self.whitespace()
        return out

    def parse(self):
        rules = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except AssertionError:
                why = self.ignore_until(["}"])
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules


INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
}


def style(node, rules):
    node.style = {}
    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value
    for selector, body in rules:
        if not selector.matches(node):
            continue
        for property, value in body.items():
            computed_value = compute_style(node, property, value)
            if not computed_value:
                continue
            node.style[property] = computed_value
    if isinstance(node, Element) and "style" in node.attributes:
        pairs = CSSParser(node.attributes["style"]).body()
        for property, value in pairs.items():
            computed_value = compute_style(node, property, value)
            if not computed_value:
                continue
            node.style[property] = computed_value
    for child in node.children:
        style(child, rules)


def tree_to_list(tree, list):
    list.append(tree)
    for child in tree.children:
        tree_to_list(child, list)
    return list


def resolve_url(url, current):
    if "://" in url:
        return url
    elif url.startswith("/"):
        scheme, hostpath = current.split("://", 1)
        host, oldpath = hostpath.split("/", 1)
        return scheme + "://" + host + url
    else:
        dir, _ = current.rsplit("/", 1)
        while url.startswith("../"):
            url = url[3:]
            if dir.count("/") == 2:
                continue
            dir, _ = dir.rsplit("/", 1)
        return dir + "/" + url


def cascade_priority(rule):
    selector, body = rule
    return selector.priority


def compute_style(node, property, value):
    if property == "font-size":
        if value.endswith("px"):
            return value
        elif value.endswith("%"):
            if node.parent:
                parent_font_size = node.parent.style["font-size"]
            else:
                parent_font_size = INHERITED_PROPERTIES["font-size"]
            node_pct = float(value[:-1]) / 100
            parent_px = float(parent_font_size[:-2])
            return str(node_pct * parent_px) + "px"
        else:
            return None
    elif property == "width" or property == "height":
        if value.startswith("-") or value == "auto":
            return "auto"
        else:
            return value
    else:
        return value


class DocumentLayout:
    def __init__(self, node):
        self.node = node
        self.parent = None
        self.children = []

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height + 2 * VSTEP

    def paint(self, display_list):
        self.children[0].paint(display_list)

    def __repr__(self):
        return "DocumentLayout()"


class BlockLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        if isinstance(self.node, Element) and self.node.tag == "li":

            self.x = self.parent.x + (2 * HSTEP)
            self.width = self.parent.width + (2 * HSTEP)

        else:
            self.x = self.parent.x
            self.width = self.parent.width

        previous = None

        for child in self.node.children:
            if isinstance(child, Element):
                if child.tag == "head":
                    continue
            if layout_mode(child) == "inline":
                next = InlineLayout(child, self, previous)
            else:
                next = BlockLayout(child, self, previous)

            self.children.append(next)
            previous = next

        if (
            self.node.style.get("width", "auto")
            and self.node.style.get("width", "auto") != "auto"
        ):
            self.width = float(self.node.style["width"][:-2])
        else:
            self.width = self.parent.width

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for child in self.children:
            child.layout()

        if self.node.style.get("height") and self.node.style.get("height") != "auto":
            self.height = float(self.node.style["height"][:-2])
        else:
            self.height = sum([child.height for child in self.children])

    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)

    def __repr__(self):
        s = "BlockLayout"
        s += (
            "(x="
            + str(self.x)
            + ", y="
            + str(self.y)
            + ", width="
            + str(self.width)
            + ", height="
            + str(self.height)
            + ")"
        )
        return s


class LineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):
        self.width = self.parent.width
        self.x = self.parent.x

        if self.previous:
            self.y = self.previous.y + self.previous.height
        else:
            self.y = self.parent.y

        for word in self.children:
            word.layout()

        if not self.children:
            self.height = 0
            return

        max_ascent = max([word.font.metrics("ascent")
                         for word in self.children])
        baseline = self.y + 1.25 * max_ascent
        for word in self.children:
            word.y = baseline - word.font.metrics("ascent")
        max_descent = max([word.font.metrics("descent")
                          for word in self.children])
        self.height = 1.25 * (max_ascent + max_descent)

    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)

    def __repr__(self):
        s = "LineLayout"
        s += (
            "(x="
            + str(self.x)
            + ", y="
            + str(self.y)
            + ", width="
            + str(self.width)
            + ", height="
            + str(self.height)
            + ")"
        )
        return s


class InputLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.children = []
        self.parent = parent
        self.previous = previous

    def layout(self):
        family = self.node.style.get("font-family", None)
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        if style == "normal":
            style = "roman"
        size = int(float(self.node.style["font-size"][:-2]) * 0.75)
        self.font = get_font(size, weight, style, family)
        self.width = INPUT_WIDTH_PX

        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = self.font.metrics("linespace")

        if self.node.attributes.get("type", "input").lower() == "checkbox":
            self.width = 16
            self.height = 16

        if self.node.attributes.get("type", "").lower() == "hidden":
            self.width = 0.0
            self.height = 0.0

    def paint(self, display_list):
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            display_list.append(rect)

        if self.node.tag == "input":
            if self.node.attributes.get("type", "").lower() == "checkbox":
                if "checked" in self.node.attributes:
                    text = "X"
                else:
                    text = ""
            elif self.node.attributes.get("type", "").lower() == "password":
                text = "*" * len(self.node.attributes.get("value", ""))
            else:
                text = ""
        elif self.node.tag == "button":
            text = self.node.attributes.get("value", "")
        elif self.node.tag == "textarea":
            text = self.node.attributes.get("value", "")
        elif self.node.tag == "h1":
            text = self.node.attributes.get("value", "")

        color = self.node.style["color"]
        display_list.append(DrawText(self.x, self.y, text, self.font, color))

    def __repr__(self):
        s = "InputLayout"
        s += (
            "(x="
            + str(self.x)
            + ", y="
            + str(self.y)
            + ", width="
            + str(self.width)
            + ", height="
            + str(self.height)
            + ")"
        )
        return s


class TextLayout:
    def __init__(self, node, word, parent, previous):
        self.node = node
        self.word = word
        self.children = []
        self.parent = parent
        self.previous = previous

    def layout(self):
        family = self.node.style.get("font-family", None)
        self.word = html.unescape(self.word)
        weight = self.node.style["font-weight"]
        style = self.node.style["font-style"]
        size = int(float(self.node.style["font-size"][:-2]))
        # self.font = get_font(size, weight, style)
        if style == "normal":
            style = "roman"
        if self.node.parent.tag.startswith("h") and len(self.node.parent.tag) == 2:
            weight = "bold"
        if self.node.parent.tag == "h1":
            size = int(size * 1.75)

        if self.node.parent.tag == "h2":
            size = int(size * 1.5)
        if self.node.parent.tag == "h3":
            size = int(size * 1.3)
        if self.node.parent.tag == "h4":
            size = int(size * 1.1)
        if self.node.parent.tag == "h5":
            size = int(size * 0.9)
        if self.node.parent.tag == "h6":
            size = int(size * 0.75)
        elif self.node.parent.tag == "b" or self.node.parent.tag == "strong":
            weight = "bold"
        elif self.node.parent.tag == "i" or self.node.parent.tag == "em":
            style = "italic"
        elif (
            self.node.parent.tag == ("pre")
            or self.node.parent.tag == ("code")
            or (
                self.node.parent.tag == ("span")
                and self.node.parent.parent.tag == ("code")
            )
        ):
            family = "JetBrains Mono"
        elif self.node.parent.tag == ("blockquote"):
            size = 14
            style = "italic"

        self.font = get_font(size, weight, style, family)
        self.width = self.font.measure(self.word)

        if self.previous:
            space = self.previous.font.measure(" ")
            self.x = self.previous.x + space + self.previous.width
        else:
            self.x = self.parent.x

        self.height = self.font.metrics("linespace")

    def paint(self, display_list):
        color = self.node.style["color"]
        anchor = "nw"
        if isinstance(self.parent.node, Element):
            if self.parent.node.tag == "li" and self.x == self.parent.x:
                if self.node.parent.tag == "a":
                    display_list.append(
                        DrawRect(
                            self.x - 20, self.y + 6, self.x - 15, self.y + 10, color
                        )
                    )
                else:
                    self.font = get_font(
                        self.node.style["font-size"][:-2],
                        self.node.style["font-weight"],
                        "italic",
                        self.node.style.get("font-family"),
                    )

        display_list.append(
            DrawText(self.x, self.y, self.word, self.font, color, anchor)
        )

    def __repr__(self):
        s = "TextLayout"
        s += (
            "(x="
            + str(self.x)
            + ", y="
            + str(self.y)
            + ", width="
            + str(self.width)
            + ", height="
            + str(self.height)
            + ", font="
            + str(self.font)
            + ")"
        )
        return s


class InlineLayout:
    def __init__(self, node, parent, previous):
        self.node = node
        self.parent = parent
        self.previous = previous
        self.children = []

    def layout(self):

        if (
            isinstance(self.node, Element)
            and self.node.tag == "li"
            or isinstance(self.node, Element)
            and self.node.tag == "pre"
        ):

            self.x = self.parent.x + (2 * HSTEP)
            self.width = self.parent.width - (4 * HSTEP)

        else:
            self.x = self.parent.x
            self.width = self.parent.width

        if (
            self.node.style.get("width", "auto")
            and self.node.style.get("width", "auto") != "auto"
        ):
            self.width = float(self.node.style["width"][:-2])
        else:
            self.width = self.parent.width

        self.y = (
            self.previous.y + self.previous.height if self.previous else self.parent.y
        )

        if isinstance(self.node, Element):
            if self.node.tag in ["h1", "h2", "h3", "h4", "h5", "h6", "p", "pre", "div"]:
                self.y += VSTEP
                if isinstance(self.previous, BlockLayout):
                    self.y += VSTEP
                elif self.node.tag == "p" and self.node.parent.tag == "div":
                    self.y += VSTEP

        elif self.node.parent.tag == "header":
            if isinstance(self.node, Text):
                self.y = self.previous.y

        self.cursor_x = self.x
        self.weight = "normal"
        self.style = "roman"
        self.size = 16
        self.centered = FALSE
        self.super = FALSE
        self.abbr = FALSE
        self.lineSize = -1e9
        self.new_line()
        self.recurse(self.node)

        for line in self.children:
            line.layout()

        self.height = sum([line.height for line in self.children])

    def paint(self, display_list):
        for child in self.children:
            child.paint(display_list)

    def recurse(self, node):
        if isinstance(node, Text):
            self.text(node)
        else:
            if node.tag == "br":
                self.new_line()

            elif node.tag == "input" or node.tag == "button":
                self.input(node)
            else:
                for child in node.children:
                    self.recurse(child)

    def input(self, node):
        w = INPUT_WIDTH_PX

        if self.cursor_x + w > self.x + self.width:
            self.new_line()
        line = self.children[-1]
        input = InputLayout(node, line, self.previous_word)
        line.children.append(input)
        self.previous_word = input
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        if style == "normal":
            style = "roman"
        size = int(float(node.style["font-size"][:-2]))
        font = get_font(size, weight, style)
        self.cursor_x += w + font.measure(" ")

    def text(self, node):
        weight = node.style["font-weight"]
        style = node.style["font-style"]
        family = node.style.get("font-family", None)
        if node.text == "":
            return
        if node.text == "\n":
            self.new_line()
            return
        if node.text == "\t":
            self.cursor_x += 4 * HSTEP
            return
        if style == "normal":
            style = "roman"
        if node.parent.tag == "b":
            node.style["font-weight"] = "bold"
            weight = "bold"

        if node.parent.tag == "i":
            node.style["font-style"] = "italic"
            style = "italic"
        if node.parent.tag == "u":
            node.style["text-decoration"] = "underline"
            style = "underline"
        if (
            node.parent.tag == "pre"
            or node.parent.tag == "code"
            or (node.parent.tag == "span" and node.parent.parent.tag == "code")
        ):
            for child in node.children:
                child.style["font-family"] = "JetBrains Mono"
                family = "JetBrains Mono"

            node.style["font-family"] = "JetBrains Mono"
            family = "JetBrains Mono"

        size = int(float(node.style["font-size"][:-2]))

        for word in node.text.split():
            font = get_font(size, weight, style, family)

            w = font.measure(word)
            # check if need to wrap words
            # if self.cursor_x + w > self.width - HSTEP:
            if self.cursor_x + w > self.x + self.width - HSTEP:
                self.new_line()
            self.cursor_x += w + font.measure(" ")

            # Add text object and append to line
            line = self.children[-1]
            text = TextLayout(node, word, line, self.previous_word)
            line.children.append(text)
            self.previous_word = text

    def new_line(self):
        self.previous_word = None
        self.cursor_x = self.x
        last_line = self.children[-1] if self.children else None
        new_line = LineLayout(self.node, self, last_line)
        self.children.append(new_line)

    def __repr__(self):
        s = "InlineLayout"
        s += (
            "(x="
            + str(self.x)
            + ", y="
            + str(self.y)
            + ", width="
            + str(self.width)
            + ", height="
            + str(self.height)
            + ")"
        )
        return s


MESSAGE_LEVEL = {"Info": "info", "Warning": "warning", "Error": "error"}
# primarily used to export functions from Python into JS


class JSContext:
    def __init__(self, tab):
        self.tab = tab
        self.tab.messages = []
        self.node_to_handle = {}
        self.handle_to_node = {}
        self.interp = dukpy.JSInterpreter()
        self.interp.export_function("log", self.log)
        self.interp.export_function("error", self.error)
        self.interp.export_function("warning", self.warning)
        self.interp.export_function("querySelectorAll", self.querySelectorAll)
        self.interp.export_function("getAttribute", self.getAttribute)
        self.interp.export_function("innerHTML_set", self.innerHTML_set)
        self.interp.export_function("getChildren", self.getChildren)
        self.interp.export_function("appendChild", self.appendChild)
        self.interp.export_function("cookie_set", self.cookie_set)
        self.interp.export_function("cookie_get", self.cookie_get)
        self.interp.export_function(
            "XMLHttpRequest_send", self.XMLHttpRequest_send)
        with open("runtime.js") as f:
            self.run(f.read())
        self.nodesWithIds = [
            node
            for node in tree_to_list(self.tab.nodes, [])
            if isinstance(node, Element) and "id" in node.attributes
        ]
        for node in self.nodesWithIds:
            handle = self.get_handle(node)
            id = node.attributes["id"]
            self.interp.evaljs(f"'var {id} = new Node({handle});'")

    def run(self, code):
        return self.interp.evaljs(code)

    def add_message(self, x, l=None, s=None):
        message = {"text": x}
        if l is not None:
            message["level"] = MESSAGE_LEVEL[l]
        else:
            message["level"] = "info"
        if s is not None:
            message["show"] = s
        else:
            message["show"] = False
        self.tab.messages.append(message)

    def log(self, x):
        self.add_message(x)

    def error(self, x):
        self.add_message(x, "Error", True)

    def warning(self, x):
        self.add_message(x, "Warning")

    def cookie_get(self):
        if self.tab.host in COOKIE_JAR:
            cookie, params = COOKIE_JAR[self.tab.host]
            if "httponly" in params:
                return ""
            else:
                return cookie
        else:
            return ""

    def cookie_set(self, s):
        if self.tab.host in COOKIE_JAR:
            cookie, params = COOKIE_JAR[self.tab.host]
            if "httponly" in params:
                return
        params = {}
        if ";" in s:
            cookie, rest = s.split(";", 1)
            for param_pair in rest.split(";"):
                if "=" in param_pair:
                    name, value = param_pair.strip().split("=", 1)
                    params[name.lower()] = value.lower()
                else:
                    name = param_pair.strip()
                    params[name.lower()] = None
        else:
            cookie = s
        COOKIE_JAR[self.tab.host] = (cookie, params)

    def createElement(self, tagName):
        elt = Element(tagName, {}, None)
        return self.get_handle(elt)

    def getChildren(self, handle):
        elt = self.handle_to_node[handle]
        return [self.get_handle(node) for node in elt.children if type(node) != Text]

    def XMLHttpRequest_send(self, method, url, body):
        full_url = resolve_url(url, self.tab.url)
        if not self.tab.allowed_request(full_url):
            raise Exception("Cross-origin XHR blocked by CSP")

        if url_origin(full_url) != url_origin(self.tab.url):
            raise Exception("Cross-origin XHR request not allowed")
        headers, out = request(full_url, self.tab.url, payload=body)
        return out

    def appendChild(self, parent, child):
        parent: Element = self.handle_to_node[parent]
        child: Element = self.handle_to_node[child]
        child.parent = parent
        parent.children.append(child)
        self.tab.render()

    def querySelectorAll(self, selector_text):
        # parse the selector and find and return all matching elements on Python side
        selector = CSSParser(selector_text).selector()
        # find all nodes matching the selector
        nodes = [
            node for node in tree_to_list(self.tab.nodes, []) if selector.matches(node)
        ]
        return [self.get_handle(node) for node in nodes]

    # Python objects identified through a numeral value. Each number represents a handle for an element
    def get_handle(self, elt):
        if elt not in self.node_to_handle:
            handle = len(self.node_to_handle)
            self.node_to_handle[elt] = handle
            self.handle_to_node[handle] = elt
        else:
            handle = self.node_to_handle[elt]
        return handle

    # Take in a handle and return element attribute
    def getAttribute(self, handle, attr):
        elt = self.handle_to_node[handle]
        return elt.attributes.get(attr, None)

    # Anytime an event occurs, will dispatch event
    def dispatch_event(self, type, elt):
        handle = self.node_to_handle.get(elt, -1)
        do_default = self.interp.evaljs(
            EVENT_DISPATCH_CODE, type=type, handle=handle)
        return not do_default

    def foo(self, arg):
        try:
            pass
        except:
            import traceback

            traceback.print_exc()
            raise

    # Parse HTML string for innerhtml
    def innerHTML_set(self, handle, s):
        doc = HTMLParser("<html><body>" + s + "</body></html>").parse()
        new_nodes = doc.children[0].children
        elt = self.handle_to_node[handle]
        elt.children = new_nodes
        for child in elt.children:
            child.parent = elt
        self.tab.render()


def url_origin(url):
    scheme_colon, _, host, _ = url.split("/", 3)
    return scheme_colon + "//" + host


def request(url, top_level_url, headers=None, payload=None):
    original_url = url
    if "about:bookmarks" in url:
        doctype = "<!doctype html>\r\n"
        urls = ""

        for index, url in enumerate(BOOKMARKS):
            if index < (len(BOOKMARKS) - 1):
                urls += f'<a href="{url}">{url}</a><br>\r\n'
            else:
                urls += f'<a href="{url}">{url}</a><br>'

        body = doctype + urls

        return BOOKMARKS, body

    scheme, url = url.split("://", 1)

    assert scheme in ["http", "https",
                      "file"], "Unknown scheme {}".format(scheme)

    if scheme == "file":
        with open(url, encoding="utf-8") as file:
            body = file.read()
        return headers, body

    if "#" in url:
        url = url.split("#")[0]

    host, path = url.split("/", 1)
    path = "/" + path

    if ":" in host:
        host, port = host.split(":", 1)
        port = int(port)
    elif scheme == "https":
        port = 443
    else:
        port = 80

    s = socket.socket(
        family=socket.AF_INET,
        type=socket.SOCK_STREAM,
        proto=socket.IPPROTO_TCP,
    )

    s.connect((host, port))

    if scheme == "https":
        ctx = ssl._create_unverified_context()
        # ctx = ssl.create_default_context()
        try:
            s = ctx.wrap_socket(s, server_hostname=host)
        except:
            return {
                "x-magicheader": "failed"
            }, "<!doctype html> Secure Connection Failed"

    method = "POST" if payload else "GET"

    if headers == None:
        headers = {}
    headers["Host"] = host
    headers["Connection"] = "close"

    if payload:
        length = len(payload.encode("utf8"))
        headers["Content-Length"] = length
    serviceHeaders = []
    serviceValues = []
    for k, v in headers.items():
        serviceHeaders.append(k.lower())
        serviceValues.append(v)
    if payload == None:
        payload = ""
    request = f"{method} {path} HTTP/1.1\r\n"
    for key, val in headers.items():
        key = key.lower()
        request += f"{key}: {val}\r\n"

    if host in COOKIE_JAR:
        cookie, params = COOKIE_JAR[host]
        allow_cookie = True
        if top_level_url and params.get("samesite", "none") == "lax":
            _, _, top_level_host, _ = top_level_url.split("/", 3)
            allow_cookie = host == top_level_host or method == "GET"
        if allow_cookie:
            request += "Cookie: {}\r\n".format(cookie)

    request += "\r\n" + payload

    beforeRequest = time.perf_counter()
    s.send(request.encode("utf-8"))
    afterRequest = time.perf_counter()
    REQUEST_LIST.append(
        f"{original_url}\t{afterRequest - beforeRequest:0.4f}s")

    response = s.makefile("r", encoding="utf8", newline="\r\n")
    statusline = response.readline()
    version, status, explanation = statusline.split(" ", 2)

    while True:
        line = response.readline()
        if line == "\r\n":
            break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()

    if status.startswith("3"):
        newUrl = headers["location"]
        if newUrl.startswith("/"):
            newUrl = scheme + "://" + host + ":" + str(port) + newUrl
        headers, body = request(newUrl)

    if "set-cookie" in headers:
        params = {}
        if ";" in headers["set-cookie"]:
            cookie, rest = headers["set-cookie"].split(";", 1)
            for param_pair in rest.split(";"):
                if "=" in param_pair:
                    name, value = param_pair.strip().split("=", 1)
                    params[name.lower()] = value.lower()
                else:
                    name = param_pair.strip()
                    params[name.lower()] = None
        else:
            cookie = headers["set-cookie"]
        COOKIE_JAR[host] = (cookie, params)

    body = response.read()
    s.close()
    return headers, body


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 2:
        Browser().load(sys.argv[1])
    else:
        Browser().load("https://browser.engineering/")
        # Browser().load("file:////Users/adam/Projects/GitHub/CHRIS_BORDOY-main/test.html")

    tkinter.mainloop()
