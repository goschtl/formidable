# -*- coding: utf-8 -*-
"""Generated Pydantic model."""

from datetime import date
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import PydanticCustomError

class LD_000_0V1100Model(BaseModel):
    """Rückfrage nach Unfallbetrieb

    Da wir nicht feststellen können, ob wir für Ihre Betreuung zuständig sind, bitten wir Sie, die nachfolgenden Fragen zu beantworten. Wir benötigen Ihre Angaben zur Entscheidung, ob und welche Leistungen wir zu erbringen haben. Die Beantwortung der Fragen wird nur kurze Zeit in Anspruch nehmen.
    """

    # fs_unternehmensnummer's pattern uses a lookahead
    model_config = ConfigDict(regex_engine="python-re")

    aktenzeichen: Optional[str] = Field(title='Aktenzeichen:', default=None,)
    fs_schreibweise_name: str = Field(..., title='Die genaue Schreibweise meines Namens lautet:', description='vollständiger Name',)
    fs_geburtsdatum: date = Field(..., title='Mein Geburtsdatum lautet:',)
    fs_unfall_in_berufsb_einrichtung: Literal['Nein', 'Ja'] = Field(..., title='Ist der Unfall im Zusammenhang mit dem Besuch einer berufsbildenden Einrichtung eingetreten?',)
    fs_name_anschrift_einrichtung: Optional[str] = Field(title='Name und vollständige Anschrift der berufsbildenden Einrichtung:', default=None,)
    fs_firma_uzeitpunkt: str = Field(..., title='In welchem Unternehmen waren Sie zur Zeit des Unfalls beschäftigt?', description='Name und vollständige Anschrift des Hauptsitzes des Unternehmens.',)
    fs_betriebsstaette: Optional[str] = Field(title='Wie lautet ggf. die vollständige Anschrift der Betriebsstätte (Filiale) des Unternehmens, in der Sie tatsächlich eingesetzt werden?', description='Name und vollständige Anschrift der Betriebsstätte (Filiale).', default=None,)
    fs_branche: str = Field(..., title='Art (Branche) des Unternehmens?', json_schema_extra={'example': 'z.B. Textilfabrik, Holzfabrik, Maschinenfabrik, Landwirtschaft, Baugeschäft, usw.'},)
    fs_uvt: Literal['Berufsgenossenschaft der Bauwirtschaft', 'Berufsgenossenschaft Energie Textil Elektro Medienerzeugnisse', 'Berufsgenossenschaft Holz und Metall', 'Berufsgenossenschaft Verkehrswirtschaft Post-Logistik Telekommunikation', 'Berufsgenossenschaft Handel und Warenlogistik', 'Berufsgenossenschaft Nahrungsmittel und Gastgewerbe', 'Berufsgenossenschaft Rohstoffe und chemische Industrie', 'Berufsgenossenschaft für Gesundheitsdienst und Wohlfahrtspflege', 'Verwaltungs-Berufsgenossenschaft', 'Sozialversicherung Landwirtschaft, Forst und Garten', 'Bayerische Landesunfallkasse', 'Braunschweigischer Gemeindeunfallversicherungsverband', 'Feuerwehr-Unfallkasse Brandenburg', 'Feuerwehr-Unfallkasse Mitte', 'Feuerwehr-Unfallkasse Niedersachsen', 'Gemeinde-Unfallversicherungsverband Hannover', 'Gemeinde-Unfallversicherungsverband Oldenburg', 'Hanseatische Feuerwehr-Unfallkasse Nord', 'Kommunale Unfallversicherung Bayern', 'Landesunfallkasse Niedersachsen', 'Unfallkasse Brandenburg', 'Unfallkasse Berlin', 'Unfallkasse Freie Hansestadt Bremen', 'Unfallkasse Baden-Württemberg', 'Unfallkasse Hessen', 'Unfallkasse Mecklenburg-Vorpommern', 'Unfallkasse Nord', 'Unfallkasse Nordrhein-Westfalen', 'Unfallkasse Rheinland-Pfalz', 'Unfallkasse Saarland', 'Unfallkasse Sachsen', 'Unfallkasse Sachsen-Anhalt', 'Unfallkasse Thüringen', 'Unfallversicherung Bund und Bahn'] = Field(..., title='Zuständiger Unfallversicherungsträger für das Unternehmen?',)
    fs_unternehmensnummer: Optional[str] = Field(title='Wie lautet die Unternehmensnummer des Unternehmens bei diesem Unfallversicherungsträger?', description='Bitte beim Arbeitgeber erfragen.', pattern='^(?!.*[1][ ]?[2][ ]?[3][ ]?[4][ ]?[1][ ]?[2][ ]?[3][ ]?[4][ ]?[1][ ]?[2][ ]?[3][ ]?[4][ ]?[0][ ]?[0][ ]?[1][ ]?)([0-9][ ]?){14}([0-9]){1}$', default=None,)

    @model_validator(mode="after")
    def validate_dependencies(self):
        """Validate field dependencies."""
        errors = []
        if self.fs_unfall_in_berufsb_einrichtung == 'Ja':
            if self.fs_name_anschrift_einrichtung is None:
                errors.append({
                    "type": PydanticCustomError("missing", "Field required"),
                    "loc": ("fs_name_anschrift_einrichtung",),
                    "input": None,
                })
        if errors:
            raise ValidationError.from_exception_data(type(self).__name__, errors)
        return self
