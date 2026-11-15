__author__ = 'Pablo Ramos Criado'
__students__ = 'Senén y Daniel'

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
from geojson import Point
from typing import Generator, Any, Self
from bson.objectid import ObjectId
from random import randint
import yaml
import time

import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from pymongo.collection import Collection
from pymongo.cursor import Cursor
from pymongo.command_cursor import CommandCursor


def getLocationPoint(address: str) -> Point:
    location = None
    intentos = 0
    while location is None and intentos < 5:
        intentos += 1
        try:
            time.sleep(0.25)
            location = Nominatim(user_agent=str(randint(0,1000))).geocode(address)
            if location: return Point([location.longitude, location.latitude])
        except GeocoderTimedOut: continue
    raise ValueError('No se pudieron obtener coordenadas')


class Model:
    _required_vars: set[str]
    _admissible_vars: set[str]
    _location_var: str | None = None
    _modified_vars: set[str] = set()
    _db: Collection
    _internal_vars: set[str] = frozenset(('_modified_vars', '_required_vars', '_admissible_vars', '_db', '_data', '_location_var'))

    def __init__(self, **kwargs: dict[str, str | dict | list]) -> None:
        # rechazar no permitidos
        for k in kwargs.keys():
            if k not in self._required_vars and k not in self._admissible_vars and k != self._location_var and k != '_id':
                raise AttributeError(f'\'{k}\' not allowed in {self.__class__.__name__}')
        # comprobar que no faltan requeridos
        missing = self._required_vars - kwargs.keys()
        if missing: 
            raise AttributeError(f'Missing required vars: {missing}')
        # si todo está bien, asignar
        self._data = kwargs

    def __setattr__(self, name: str, value: str | dict) -> None:
        if name in self._internal_vars:
            super().__setattr__(name, value)
            return 
        # validar que sea admisible
        if name not in (self._required_vars | self._admissible_vars) and name != self._location_var:
            raise AttributeError(f"'{name}' not allowed in {self.__class__.__name__}")
        # actualizar
        self._data[name] = value
        self._modified_vars.add(name)

    def __getattr__(self, name: str) -> Any:
        if name in self._internal_vars: 
            return super().__getattribute__(name)
        try: return self._data[name]
        except KeyError: raise AttributeError(f'{name} not valid for {self.__class__.__name__}')

    def __str__(self) -> str:
        return f'{self.__class__.__name__}: {self._data}'
        
    def save(self) -> None:
        # handle location
        if self._location_var and self._location_var in self._data:
            loc_field = f'{self._location_var}_loc'
            self._data[loc_field] = getLocationPoint(self._data[self._location_var])
            self._modified_vars.add(loc_field)
        # update solo campos modificados, sino hacer insert
        if '_id' in self._data:
            update_fields = {k: self._data[k] for k in self._modified_vars}
            self._db.update_one({'_id': self._data['_id']}, {'$set': update_fields})
        else: self._db.insert_one(self._data)
        self._modified_vars.clear()

    def delete(self) -> None:
        self._db.delete_one({'_id': self._data['_id']})
    
    @classmethod
    def find(cls, filter: dict[str, str | dict]) -> Any:
        return ModelCursor(cls, cls._db.find(filter)) # Bueno tiene que devoler ModelCursor no Cursor

    @classmethod
    def aggregate(cls, pipeline: list[dict]) -> CommandCursor:
        return cls._db.aggregate(pipeline)
    
    @classmethod
    def find_by_id(cls, id: str) -> Self | None:
        """ 
        NO IMPLEMENTAR HASTA EL TERCER PROYECTO
        Busca un documento por su id utilizando la cache y lo devuelve.
        Si no se encuentra el documento, devuelve None.

        Parameters
        ----------
            id : str
                id del documento a buscar
        Returns
        -------
            Self | None
                Modelo del documento encontrado o None si no se encuentra
        """ 
        #TODO
        pass

    @classmethod
    def init_class(cls, db_collection: Collection, indexes: dict[str,str], required_vars: set[str], admissible_vars: set[str], location_var: str | None) -> None:
        cls._db = db_collection
        cls._required_vars = set(required_vars)
        cls._admissible_vars = set(admissible_vars)
        cls._location_var = location_var

        for index in indexes:
            cls._db.create_index([(index, pymongo.DESCENDING)])

        if cls._location_var:    
            loc_field = f'{cls._location_var}_loc'
            cls._db.create_index([(loc_field, pymongo.GEOSPHERE)])


class ModelCursor:
    def __init__(self, model_class: Model, cursor: Cursor):
        self.model = model_class
        self.cursor = cursor
    
    def __iter__(self) -> Generator:
        for doc in self.cursor: 
            yield self.model(**doc)


def initApp(definitions_path: str = "./models.yml", mongodb_uri="mongodb://localhost:27017/", db_name="abd", scope=globals()) -> None:
    client = MongoClient(mongodb_uri, server_api=ServerApi('1'))
    db = client[db_name]

    with open(definitions_path, 'r') as f:
        data_dict = yaml.safe_load(f.read())

    for k,v in data_dict.items():
        scope[k] = type(str(k), (Model,),{})
        scope[k].init_class(
            db_collection=db.get_collection(k), 
            indexes=v['unique_indexes'], 
            required_vars=v['required_vars'], 
            admissible_vars=v['admissible_vars'],
            location_var=v['location_index']
        )


if __name__ == '__main__':
    initApp(db_name='envivo')

    # # 1. Crear modelo
    # print("\n[1] Crear modelo (Recinto)")
    #
    # r = Recinto(
    #     nombre="M-M-M-Mayback Mewsic", 
    #     aforo=1000, 
    #     direccion="Retiro, Madrid"
    # )
    #
    # print(f"Objeto creado: {r}")
    # print(f"_modified_vars: {r._modified_vars}")   # debe estar vacío
    #
    # # 2. Asignar nuevo valor a variable admitida
    #
    # print("\n[2] Asignar valor a variable admitida ('zonas')")
    # r.zonas = {"VIP": 200, "General": 14800}
    # print(f"_modified_vars: {r._modified_vars}") 
    #
    # # 3. Asignar nuevo valor a variable NO admitida (debe fallar)
    #
    # print("\n[3] Asignar valor a variable NO admitida")
    # try:
    #     r.mememememememeybackmusic = "MEMEMEMEMEMEYBACKMEWSIC"
    #     print("ERROR: no se ha lanzado AttributeError")
    # except AttributeError as e:
    #     print(f"Rechazado correctamente: {e}")
    #
    # # 4. Guardar (insert)
    #
    # print("\n[4] Guardar (insert)")
    # r.save()
    # print(f"Objeto tras save: {r}")
    # print(f"_id asignado: {r._id}")
    # print(f"_modified_vars tras save: {r._modified_vars}")  # vacío
    #
    # # 5. Asignar nuevo valor a variable admitida
    #
    # print("\n[5] Modificar 'aforo'")
    # r.aforo = 16000
    # print(f"_modified_vars: {r._modified_vars}") # aparece aforo
    #
    # # 6. Guardar (tras un update)
    #
    # print("\n[6] Guardar (update)")
    # r.save()
    # print(f"_modified_vars tras save: {r._modified_vars}")  # Ya no debe aparecer aforo
    #
    # # 7. Buscar con find
    #
    # print("\n[7] Buscar con find")
    # cursor = Recinto.find({"nombre": "M-M-M-Mayback Mewsic"})
    #
    # # 8. Obtener primer documento (y comprobar tipo)
    #
    # print("\n[8] Obtener primer documento del cursor")
    # resultados = list(cursor)
    # if resultados:
    #     primero = resultados[0]
    #     print(f"Tipo del resultado: {type(primero).__name__}")   # Recinto
    #     print(f"Contenido: {primero}")
    #     print(f"Es un objeto Model: {isinstance(primero, Model)}")
    #
    # # 9. Modificar variable admitida del documento encontrado
    #
    # print("\n[9] Modificar 'servicios' del documento encontrado")
    # primero.servicios = ["mememeyback-bar", "mememememerchandising"]
    # print(f"_modified_vars: {primero._modified_vars}")   # debería salir servicios
    #
    # # 10. Guardar
    #
    # print("\n[10] Guardar el documento modificado (update)")
    # primero.save()
    # print(f"_modified_vars tras save: {primero._modified_vars}")
    #
    # # 11. Eliminar
    #
    # print("\n[11] Eliminar el documento")
    # primero.delete()
    # print(f"Documento eliminado")
    #
    # # 12. Probar getLocationPoint 
    #
    # print("\n[12] getLocationPoint")
    # try:
    #     p = getLocationPoint("Puerta del Sol, Madrid")
    #     print(f"Punto obtenido: {p}")
    #     print(f"Tipo: {type(p).__name__}")  
    # except ValueError as e:
    #     print(f"No se pudo geolocalizar: {e}")
    #
    # try:
    #     getLocationPoint("askjdhaskjdhaskjdh no existe")
    #     print("ERROR: debería haber lanzado ValueError")
    # except ValueError as e:
    #     print(f"ValueError lanzado correctamente para dirección inexistente")
    #
    # # ==========================================
    # # 1. RECINTOS
    # # ==========================================
    # r1 = Recinto(
    #     nombre="WiZink Center",
    #     aforo=17453,
    #     direccion="Avenida de Felipe II, Madrid",
    #     servicios=["Bares", "Ropero", "Parking"]
    # )
    # r1.save()
    #
    # r2 = Recinto(
    #     nombre="Palau Sant Jordi",
    #     aforo=17960,
    #     direccion="Passeig Olimpic, Barcelona"
    # )
    # r2.save()
    #
    # r3 = Recinto(
    #     nombre="Santiago Bernabeu",
    #     aforo=85000,
    #     direccion="Avenida de Concha Espina 1, Madrid",
    #     zonas={"Fondo Norte": 20000, "Tribuna": 15000, "Pista": 50000} 
    # )
    # r3.save()
    #
    # # ==========================================
    # # 2. ARTISTAS
    # # ==========================================
    # a1 = Artista(
    #     nombre="Rosalía",
    #     pais_origen="España",
    #     generos=["Pop", "Flamenco", "Urbano"],
    #     ano_inicio=2013
    # )
    # a1.save()
    #
    # a2 = Artista(
    #     nombre="Daft Punk",
    #     pais_origen="Francia",
    #     generos=["Electronic", "Dance"],
    #     ano_inicio=1993
    # )
    # a2.save()
    #
    # a3 = Artista(
    #     nombre="The Rolling Stones",
    #     pais_origen="Reino Unido",
    #     generos=["Rock", "Blues"],
    #     ano_inicio=1962
    # )
    # a3.save()
    #
    # # ==========================================
    # # 3. EVENTOS
    # # ==========================================
    # e1 = Evento(
    #     titulo="Motomami World Tour - Madrid",
    #     artistas=[a1._id], 
    #     recinto=r1._id,
    #     fecha_hora="2023-07-19 21:30:00",
    #     precio_zona={"General": 60, "VIP": 150},
    #     entradas_vendidas=17000
    # )
    # e1.save()
    #
    # e2 = Evento(
    #     titulo="Alive 2027", 
    #     artistas=[a2._id], 
    #     recinto=r2._id,
    #     fecha_hora="2027-08-14 22:00:00",
    #     precio_zona={"General": 80, "Pista": 120},
    #     entradas_vendidas=17960
    # )
    # e2.save()
    #
    # e3 = Evento(
    #     titulo="Hackney Diamonds Tour",
    #     artistas=[a3._id], 
    #     recinto=r3._id,
    #     fecha_hora="2024-06-20 21:00:00",
    #     precio_zona={"Grada": 90, "Pista": 130, "VIP": 350},
    #     entradas_vendidas=80000
    # )
    # e3.save()
    #
    # # ==========================================
    # # 4. ASISTENTES
    # # ==========================================
    # as1 = Asistente(
    #     nombre="Laura Gómez",
    #     email="laura.gomez@example.com",
    #     fecha_alta="2023-01-15",
    #     direccion="Plaza Mayor, Madrid",
    #     preferencias_genero=["Pop", "Indie"]
    # )
    # as1.save()
    #
    # as2 = Asistente(
    #     nombre="Carlos Ruiz",
    #     email="carlos.ruiz@example.com",
    #     fecha_alta="2022-11-05",
    #     direccion="Puerta del Sol, Madrid",
    #     preferencias_genero=["Rock", "Metal"]
    # )
    # as2.save()
    #
    # as3 = Asistente(
    #     nombre="María Fernández",
    #     email="maria.fer@example.com",
    #     fecha_alta="2024-02-20",
    #     direccion="Retiro, Madrid",
    #     preferencias_genero=["Electronic"]
    # )
    # as3.save()
    #
