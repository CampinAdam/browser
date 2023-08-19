LISTENERS = {}

//JavaScript Runtime file. We run this before any user code
console = {
    log: function (x) {
        call_python("log", x);
    },
    warn: function (x) {
        call_python("warning", x);
    },
    error: function (x) {
        call_python("error", x);
    },
    assert: function (x) {
        if (!x) {
            call_python("error", "Assertion failed")

        }
    }
}

var x = 2

//Node object that wraps a handle
function Node(handle) {
    this.handle = handle;
}

//Create an event object for eventlisteners
function Event(type) {
    this.type = type
    this.do_default = true;
}

function XMLHttpRequest() {
}

XMLHttpRequest.prototype.open = function (method, url, is_async) {
    if (is_async) throw Error("Asynchronous XHR is not supported");
    this.method = method;
    this.url = url;
};

XMLHttpRequest.prototype.send = function (body) {
    this.responseText = call_python(
        "XMLHttpRequest_send",
        this.method,
        this.url,
        this.body
    );
};

function foo() {
    try {
        y + 2
    } catch (e) {
        console.log("Crash in function %s", e.stack);
        throw e;
    }
}

//The event objects will have a prevent default function
Event.prototype.preventDefault = function () {
    this.do_default = false;
}

//Maps handles to a dictionary that maps event types to a list of listeners
Node.prototype.addEventListener = function (type, listener) {
    if (!LISTENERS[this.handle]) LISTENERS[this.handle] = {};
    var dict = LISTENERS[this.handle];
    if (!dict[type]) dict[type] = [];
    var list = dict[type];
    list.push(listener);
}

//Dispatches event by looking up the type and handle in the LISTENERS array
Node.prototype.dispatchEvent = function (evt) {
    var type = evt.type;
    var handle = this.handle;
    var list = (LISTENERS[handle] && LISTENERS[handle][type]) || [];
    for (var i = 0; i < list.length; i++) {
        list[i].call(this, evt);
    }
    return evt.do_default;
}

//Create Node objects
document = {
    createElement: function (s) {
        var handle = call_python("createElement", s)
        return new Node(handle)
    },
    querySelectorAll: function (s) {
        var handles = call_python("querySelectorAll", s);
        return handles.map(function (h) {
            return new Node(h)
        });
    }
}

//Get value of HTML Attributes by taking Nodes in JS and translate them to handles for Python
Node.prototype.getAttribute = function (attr) {
    return call_python("getAttribute", this.handle, attr);
}

Node.prototype.appendChild = function (aChild) {
    return call_python("appendChild", this.handle, aChild);
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("change", lengthCheck);
}

//Updates character count every time an input area changes
function lengthCheck() {
    var name = this.getAttribute("name");
    var value = this.getAttribute("value");
    if (value.length > 100) {
        console.log("Input " + name + " has too much text.")
    }
}

var inputs = document.querySelectorAll("input");
for (var i = 0; i < inputs.length; i++) {
    inputs[i].addEventListener("change", lengthCheck);
}

//takes in a string, parses it as HTML, and makes the new parsed HTML nodes children of the original node
Object.defineProperty(Node.prototype, 'innerHTML', {
    set: function (s) {
        call_python("innerHTML_set", this.handle, s.toString());
    }
});

Object.defineProperty(document, 'cookie', {
    set: function (s) {
        call_python("cookie_set", s.toString());
    },
    get: function () {
        return call_python("cookie_get");
    }
});

Object.defineProperty(Node.prototype, "children", {
    get: function () {
        var handles = call_python("getChildren", this.handle);
        return handles.map(function (h) {
            return new Node(h);
        });
    },
});