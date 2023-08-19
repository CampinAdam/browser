label = document.querySelectorAll("label")[0];

allow_submit = true;

function lengthCheck() {
    allow_submit = input.getAttribute("value").length <= 100;
    if (!allow_submit) {
        // ...
    }
}

form = document.querySelectorAll("form")[0];
form.addEventListener("submit", function(e) {
    if (!allow_submit) e.preventDefault();
});
input = document.querySelectorAll("input")[0];
input.addEventListener("keydown", lengthCheck);