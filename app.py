import os
import subprocess
import time
from datetime import datetime, date, timezone, timedelta
from flask import Flask, render_template, request
from pathlib import Path

import locale

import webbrowser
from urllib.parse import quote

import caldav
from icalendar import Calendar, Event
from dotenv import load_dotenv

locale.setlocale(locale.LC_TIME, "it_IT.UTF-8")

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(dotenv_path=BASE_DIR / "env" / ".env")

APPLE_ID = os.environ["APPLE_ID"]
APPLE_APP_PASSWORD = os.environ["APPLE_APP_PASSWORD"]

name2phone = {
    "bigucci_alessandro": ("393287564035", "Topi"),
    "bellone_emanuela": ("393292517443", "Manu"),
}


def extract_people_from_description(description_list):
    """
    Estrae coppie nome/cognome dalla descrizione.
    Supporta:
    - Singola persona: "mario rossi"
    - Multiple persone separate da ";": "mario rossi; luigi bianchi"
    - Multiple persone separate da ",": "mario rossi, luigi bianchi"
    """
    if not description_list or len(description_list) < 2:
        return []

    people = []

    # Se la descrizione contiene separatori (;), dividi per separatore
    full_text = " ".join(description_list)

    # Prova con separatore ";"
    if ";" in full_text:
        parts = [p.strip() for p in full_text.split(";")]
    # Prova con separatore ","
    elif "," in full_text:
        parts = [p.strip() for p in full_text.split(",")]
    else:
        # Singola persona: prendi primi 2 elementi come nome + cognome
        parts = [full_text]

    for part in parts:
        words = part.split()
        if len(words) >= 2:
            # Estrai nome (primo) e cognome (secondo)
            nome = words[0]
            cognome = words[1]
            people.append((nome, cognome))

    return people


def find_person_in_directory(nome, cognome, name2phone):
    """
    Cerca una persona nel dizionario name2phone.
    Prova: "cognome_nome" e "nome_cognome"
    """
    # Prova cognome_nome (formato usato nel tuo dizionario)
    desc_1 = f"{cognome}_{nome}"
    if desc_1.lower() in name2phone:
        return name2phone[desc_1.lower()], desc_1

    # Prova nome_cognome
    desc_2 = f"{nome}_{cognome}"
    if desc_2.lower() in name2phone:
        return name2phone[desc_2.lower()], desc_2

    return None, None


def calendar_do():
    # Connessione a iCloud CalDAV
    client = caldav.DAVClient(
        url="https://caldav.icloud.com",
        username=APPLE_ID,
        password=APPLE_APP_PASSWORD,
    )

    # Recupera il profilo CalDAV
    principal = client.get_principal()

    # Elenca i calendari disponibili
    calendars = principal.get_calendars()

    if not calendars:
        raise RuntimeError("Nessun calendario iCloud trovato")

    # print("Calendari disponibili:")
    # for index, calendar in enumerate(calendars):
    #     print(f"{index}: {calendar.get_display_name()}")

    cal_wa_links = []
    for calendar in calendars:
        name_cal = calendar.get_display_name()
        if name_cal == "Personal" or name_cal == "Trattamento":

            print(f"Uso il calendario: {name_cal}")

            start = datetime.now()
            end = start + timedelta(days=2)

            now = datetime.now(tz=timezone.utc)
            tomorrow_00 = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            start = tomorrow_00
            end = tomorrow_00 + timedelta(days=1)

            events = calendar.search(
                start=start,
                end=end,
                event=True,
                expand=True,
            )

            for event in events:
                component = event.icalendar_component

                # print("Chiavi disponibili:")
                # print(list(component.keys()))

                title = str(component.get("SUMMARY"))

                # Estrai DESCRIPTION in modo safe
                description_raw = component.get("DESCRIPTION")
                if description_raw:
                    description = str(description_raw).lower().split()
                else:
                    description = []

                start = (
                    component.get("DTSTART").dt.strftime("%A %d/%m/%Y %H:%M").split()
                )
                end = component.get("DTEND").dt.strftime("%A %d/%m/%Y %H:%M")

                print(
                    f"Titolo: {title} Nota: {description} Inizio: {start} Fine: {end}"
                )

                if description:
                    if len(description) >= 2:
                        people = extract_people_from_description(description)

                        if people:
                            for nome, cognome in people:
                                person_info, desc = find_person_in_directory(
                                    nome, cognome, name2phone
                                )

                                if person_info:
                                    phone, nomignolo = person_info
                                    message = f"""Memo: {name_cal} domani {start[1]} ore {start[2]}"""
                                    link = (
                                        f"https://wa.me/{phone}?text={quote(message)}"
                                    )
                                    cal_wa_links.append(
                                        {
                                            "link": link,
                                            "title": title,
                                            "nome": nome,
                                            "cognome": cognome,
                                            "start": start,
                                            "end": end,
                                            "calendar": name_cal,
                                            "found": True,
                                        }
                                    )
                                else:
                                    print(
                                        f"Persona non trovata in rubrica: {nome} {cognome}"
                                    )
                                    cal_wa_links.append(
                                        {
                                            "link": None,
                                            "title": title,
                                            "nome": nome,
                                            "cognome": cognome,
                                            "start": start,
                                            "end": end,
                                            "calendar": name_cal,
                                            "found": False,
                                        }
                                    )
                        else:
                            print(
                                "Nelle note dell'appuntamento ci devono essere nome e cognome dell'allievo"
                            )
                            cal_wa_links.append(
                                {
                                    "link": None,
                                    "title": title,
                                    "nome": description,
                                    "cognome": "",
                                    "start": start,
                                    "end": end,
                                    "calendar": name_cal,
                                    "found": False,
                                }
                            )
                    else:
                        print(
                            "Nelle note dell'appuntamento ci devono essere nome e cognome dell'allievo"
                        )
                        cal_wa_links.append(
                            {
                                "link": None,
                                "title": title,
                                "nome": str(description_raw),
                                "cognome": "",
                                "start": start,
                                "end": end,
                                "calendar": name_cal,
                                "found": False,
                            }
                        )
                else:
                    print("Note dell'appuntamento vuoto")
                    cal_wa_links.append(
                        {
                            "link": None,
                            "title": title,
                            "nome": "Mancano il nome e cognome nelle note",
                            "cognome": "",
                            "start": start,
                            "end": end,
                            "calendar": name_cal,
                            "found": False,
                        }
                    )
    return cal_wa_links


app = Flask(__name__)


@app.route("/")
def timer():
    return render_template("Timer.html")


@app.route("/CountDate", methods=["GET", "POST"])
def count_date():
    result = None
    error = None

    if request.method == "POST":
        try:
            start_date = date.fromisoformat(request.form["start_date"])
            days = int(request.form["days"])

            if days <= 0:
                raise ValueError

            result = start_date + timedelta(days=days - 1)

        except (ValueError, TypeError):
            error = "Inserisci una data valida e un numero di giorni maggiore di zero."

    return render_template(
        "CountDate.html",
        result=result,
        error=error,
    )


@app.route("/Appointments", methods=["GET", "POST"])
def appointments():
    results = []
    error = None

    if request.method == "POST":
        results = calendar_do()
        # print(results)

    return render_template(
        "Appointments.html",
        results=results,
        error=error,
    )


if __name__ == "__main__":
    # Avvia Flask come processo separato
    flask_process = subprocess.Popen(
        [
            "python",
            "-m",
            "flask",
            "run",
            "--debug",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ],
        cwd=BASE_DIR,
    )

    time.sleep(1)  # Aspetta che Flask si avvii
    # webbrowser.open("http://127.0.0.1:8000")

    try:
        flask_process.wait()
    except KeyboardInterrupt:
        flask_process.terminate()
