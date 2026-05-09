# HR Contract Module Agent v2

Stabilerer Mini-MVP für HR-lastiges Vertragsmanagement.

## Fokus

Dieses Tool erstellt keine finale Rechtsberatung, sondern strukturierte interne Entwürfe für HR und Legal.

Es zeigt:
- Textbausteine je Thema
- Fachbereichslogik
- Corporate Header und Footer
- Fallanalyse
- fehlende Informationen
- HR-/Legal-Checkliste
- Vertrags-/HR-Entwurf
- JSON Export

## Start

```bash
pip3 install -r requirements.txt
streamlit run app.py
```

## Wichtige Verbesserung gegenüber v1

Die Ausgabe ist stärker strukturiert:
1. Fallanalyse
2. erkannte Themen
3. fehlende Informationen
4. Fachbereichliche Hinweise
5. verwendete Textbausteine
6. Vertrags-/HR-Entwurf
7. HR-/Legal-Checkliste
8. nächste Schritte

## Weiterentwicklung

- echte HR-Datenbank anbinden
- Textbausteine versionieren
- Export als DOCX/PDF
- Freigabeprozess mit HR/Legal
- Rollen- und Berechtigungskonzept
