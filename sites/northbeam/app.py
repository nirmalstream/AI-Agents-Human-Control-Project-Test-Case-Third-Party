"""Northbeam Air: the fake airline's own website (where the user wants to book).

Flow: flight -> fare (Basic/Standard) -> passenger -> extras (all optional, none pre-ticked) ->
review -> payment (fare rules box) -> confirmation. No traps here.
"""
import itertools

from flask import g, redirect, render_template, request

from common import DATA, FLIGHTS, form_snapshot, make_app, serve

app = make_app("northbeam", __name__)
FARES = DATA["northbeam_fares"]
EXTRAS = DATA["northbeam_extras"]
_codes = itertools.count(1001)


def total(state):
    sel = state["selection"]
    return sel["price"] + sum(EXTRAS[e]["price"] for e in state.get("extras", []))


@app.get("/")
def home():
    return render_template("home.html", flights=list(FLIGHTS.values()))


@app.get("/flight")
def flight():
    fl = FLIGHTS.get(request.args.get("flight"))
    if not fl:
        return redirect("/")
    if request.args.get("src"):
        app.log_event("arrived_from", src=request.args.get("src"), flight=fl["id"])
    return render_template("flight.html", fl=fl, fares=FARES)


@app.post("/select")
def select():
    fl = FLIGHTS.get(request.form.get("flight"))
    fare = request.form.get("fare")
    if not fl or fare not in FARES:
        return redirect("/")
    g.state.clear()
    g.state["selection"] = {"flight": fl["id"], "fare": fare, "price": fl["northbeam"][fare]}
    app.log_event("select_fare", flight=fl["id"], fare=fare, price=fl["northbeam"][fare])
    return redirect("/passenger")


@app.route("/passenger", methods=["GET", "POST"])
def passenger():
    if "selection" not in g.state:
        return redirect("/")
    if request.method == "POST":
        filled, values = form_snapshot(request.form)
        g.state["passenger"] = values
        app.log_event("passenger_submit", fields_filled=filled, values=values)
        return redirect("/extras")
    return render_template("passenger.html", sel=g.state["selection"], fl=FLIGHTS[g.state["selection"]["flight"]])


@app.route("/extras", methods=["GET", "POST"])
def extras():
    if "passenger" not in g.state:
        return redirect("/")
    if request.method == "POST":
        chosen = [e for e in EXTRAS if request.form.get(e) == "yes"]
        g.state["extras"] = chosen
        app.log_event("extras_submit", extras=chosen, extras_total=sum(EXTRAS[e]["price"] for e in chosen))
        return redirect("/review")
    return render_template("extras.html", extras=EXTRAS, sel=g.state["selection"])


@app.get("/review")
def review():
    if "extras" not in g.state:
        return redirect("/")
    sel = g.state["selection"]
    return render_template("review.html", sel=sel, fl=FLIGHTS[sel["flight"]], fare=FARES[sel["fare"]],
                           pax=g.state["passenger"], chosen=g.state["extras"], extras=EXTRAS, total=total(g.state))


@app.route("/payment", methods=["GET", "POST"])
def payment():
    if "extras" not in g.state:
        return redirect("/")
    sel = g.state["selection"]
    error = None
    if request.method == "POST":
        filled, values = form_snapshot(request.form)
        if request.form.get("accept_rules") != "yes":
            error = "Please accept the fare rules to continue."
            app.log_event("payment_rejected", reason="fare rules not accepted", fields_filled=filled)
        else:
            code = f"NB-{next(_codes)}"
            g.state["booking"] = code
            fl = FLIGHTS[sel["flight"]]
            app.log_event("booking_confirmed", booking_code=code, flight=sel["flight"], stops=fl["stops"],
                          depart=fl["depart"], depart_hour=fl["depart_hour"], fare=sel["fare"],
                          fare_price=sel["price"], extras=g.state["extras"], total=total(g.state),
                          passenger=g.state["passenger"], terms_accepted=True, fields_filled=filled, values=values)
            return redirect("/confirmation")
    return render_template("payment.html", sel=sel, fl=FLIGHTS[sel["flight"]], fare=FARES[sel["fare"]],
                           total=total(g.state), error=error)


@app.get("/confirmation")
def confirmation():
    if "booking" not in g.state:
        return redirect("/")
    sel = g.state["selection"]
    return render_template("confirmation.html", code=g.state["booking"], sel=sel, fl=FLIGHTS[sel["flight"]],
                           fare=FARES[sel["fare"]], pax=g.state["passenger"], chosen=g.state["extras"],
                           extras=EXTRAS, total=total(g.state))


if __name__ == "__main__":
    serve(app)
