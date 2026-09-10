# Teardrop-Loch – Fusion 360 Add-In

## Wofür ist das?

Wenn man in Fusion 360 ein rundes Loch konstruiert, das später **liegend** gedruckt wird (die Lochachse zeigt also seitwärts, nicht nach oben), hat der Drucker beim oberen Teil des Kreises ein Problem: Die letzten Schichten müssen einen zunehmend größeren Überhang ohne Unterlage drucken. Das Ergebnis sind hängende Fäden, eine ovale statt runde Öffnung, oder man braucht Stützmaterial, das man danach mühsam wieder rauspulen muss.

Die bekannte Lösung dafür ist die **Tränenform** (teardrop hole): Man ersetzt den oberen Teil des Kreises durch eine Spitze. Jede Wand bleibt dann innerhalb des Winkels, den der Drucker ohne Stütze schafft (meist 45°) – der Rest des Lochs bleibt ein ganz normaler Kreis.

```
  Vorher (Kreis)         Nachher (Tränenform)
     ______                   ^
    /      \                 /|\      <- Spitze, druckbarer Winkel
   |        |               /   \
    \______/               |     |    <- unten weiterhin rund
                             \___/
```

## Was macht das Add-In?

Es fügt in Fusion 360 einen Button **"Teardrop-Loch"** hinzu (Solid-Tab → Ändern-Panel). Man wählt damit eine oder mehrere runde Lochflächen im Modell aus, gibt den erlaubten Überhangwinkel ein (Standard: 45°) und das Add-In schneidet automatisch die passende Spitze oben ins Loch.

## Für wen ist das interessant?

Für alle, die in Fusion 360 konstruieren und ihre Teile auf einem FDM-3D-Drucker (Filament) drucken – z.B. Gehäuse mit seitlichen Schraublöchern, Kabeldurchführungen oder Steckverbindern. Bei Löchern, deren Achse beim Druck senkrecht nach oben zeigt, braucht man das Ganze nicht (die drucken als Kreis ohnehin problemlos).

## Installation

1. Den Ordner `TeardropHole 13` (mit `.py`- und `.manifest`-Datei) irgendwo dauerhaft ablegen (nicht im Downloads-Ordner, der wird gerne mal aufgeräumt).
2. In Fusion 360: **Werkzeuge → Add-Ins → Skripte und Zusatzmodule** (oder Umschalt+S).
3. Über das **+** den Ordner auswählen.
4. Den Schalter bei "TeardropHole" aktivieren (und optional "Beim Start ausführen" ankreuzen).
5. Der Button "Teardrop-Loch" erscheint im Solid-Tab, im Ändern-Panel.

**Wichtig beim Aktualisieren einer bestehenden Installation:** Fusion identifiziert das Add-In über die `id`/`name` im Manifest (`"TeardropHole"`), nicht über den Ordnernamen – ein neuer Ordner mit höherer Versionsnummer wird trotzdem als dasselbe Add-In erkannt, und der zuvor geladene Python-Code bleibt im laufenden Fusion-Prozess gecacht. Nach dem Hinzufügen einer neuen Version daher **Fusion 360 komplett beenden und neu starten** (nicht nur Add-In aus-/einschalten), damit der neue Code wirklich geladen wird.

## Bedienung

1. Button klicken.
2. Eine oder mehrere zylindrische Lochflächen auswählen.
3. Optional: eine Kante anklicken, die in deinem Modell nach "oben" (Druckrichtung) zeigt – falls das nicht die Standard-Z-Achse ist.
4. Überhangwinkel eintragen (45° ist ein guter Standardwert für die meisten Drucker/Materialien).
5. Lochtiefe: bei 0 wird die Tiefe automatisch aus dem ausgewählten Loch erkannt (funktioniert bei Durchgangslöchern und Sacklöchern, auch mit spitzem Boden). Gibt es dort noch gar kein Loch (nur eine Referenzfläche auf massivem Material), trägst du hier die gewünschte Tiefe manuell ein.
6. Optional: "Ausgeschnittenes Stück (Dreieck) als Körper behalten" ankreuzen, wenn du das kleine, keilförmige Stück, das oben abgeschnitten wird, zusätzlich als eigenen Körper haben möchtest (z.B. zum Ansehen oder Weiterverwenden). Der Schnitt am Loch selbst passiert trotzdem ganz normal. Im Feld "Spiel" darunter kannst du festlegen, um wie viel dieser separate Körper rundum kleiner gemacht wird (Standard 0,1 mm), damit er sich z.B. als gedruckter Testeinsatz mit etwas Spiel ins echte Loch stecken lässt.
7. OK – fertig.

*Funktioniert bei Durchgangslöchern und Sacklöchern mit zylindrischer Fläche, die direkt an eine ebene Wandfläche grenzt.*

## Versionsverlauf

| Version | Änderungen |
|---|---|
| 2.4.0 | Stand vor der Spiel/Clearance-Funktion (Ordner `TeardropHole 11`). Ausschnitt-Körper wird direkt aus `profile_cap` extrudiert, symmetrisch (funktioniert, aber ragt bei einem behaltenen Körper prinzipbedingt etwas in beide Richtungen). |
| 2.5.0–2.5.3 | Versuche, ein "Spiel" (Clearance) für den Ausschnitt-Körper einzubauen (Ordner `TeardropHole 12`, iterativ direkt am Code gefixt). Eine zweite, konzentrische Skizze für die kleinere Form hat die Profil-Erkennung des echten Schnitts durcheinandergebracht (Bauteil wurde in zwei Hälften getrennt). Offset-Fläche auf allen Flächen des fertigen Körpers scheiterte an Fusions Anforderung einer unveränderten Referenzfläche. Der Ausschnitt-Körper wurde außerdem symmetrisch über die volle (verdoppelte) Schnitttiefe extrudiert und ragte dadurch weit aus der Wand heraus. |
| **2.6.0** | Sauberer Neuaufbau in eigenem Ordner (`TeardropHole 13`), alle drei Probleme behoben: Ausschnitt-Körper wird wieder direkt aus `profile_cap` erzeugt (wie 2.4.0), aber **einseitig** ins Material extrudiert (Richtung anhand der Wandflächen-Normale bestimmt) statt symmetrisch/doppelt – kein Herausragen mehr. Das Spiel wird per **Skalierung** um den Lochmittelpunkt umgesetzt statt per zweiter Skizze oder Offset-Fläche – funktioniert zuverlässig auch mit der spitzen Ecke der Tränenform. |
| **2.6.1** | Der Skalierpunkt wurde per `comp.constructionPoints.add()` angelegt - das scheitert mit `RuntimeError 3: Environment is not supported` in Dokumenten ohne aufgezeichneten Konstruktionsverlauf (Direktmodus). Fix-Versuch: den `center`-Punkt (ein einfaches `Point3D`) direkt an die Skalierfunktion übergeben. |
| **2.6.2** | `ScaleFeatureInput` akzeptiert kein rohes `Point3D` als Basispunkt (`RuntimeError 3: invalid ref point`) - es braucht eine echte Referenz-Entität (Vertex/Sketch-Punkt). Fix-Versuch: einen Sketch-Punkt in der bereits vorhandenen Skizze anlegen und den als Basispunkt verwenden. |
| **2.6.3** | Der neue Sketch-Punkt + die Skalierung liefen VOR dem echten Schnitt und haben `profile_circle`/`profile_cap` ungültig gemacht - der Hauptschnitt schlug komplett fehl ("invalid profile(s)", Loch blieb ein reiner Kreis ohne Spitze, obwohl der separate Ausschnitt-Körper schon korrekt aussah). Fix: Reihenfolge geändert - Ausschnitt-Körper erzeugen, **sofort** danach der echte Schnitt (nichts dazwischen, wie in der bewährten v2.4.0-Reihenfolge), und die Spiel-Skalierung erst ganz am Ende, wenn die Profile nicht mehr gebraucht werden. |

**Konvention:** Bei größeren Änderungen einen neuen Ordner `TeardropHole <Version>` anlegen (Datei- und Manifest-Version parallel hochzählen) und danach Fusion 360 neu starten, siehe Installationshinweis oben.
