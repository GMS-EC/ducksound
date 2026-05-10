#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para mergear artistas y álbumes duplicados existentes en la BD.
Usa fuzzy matching para encontrar pares con nombres similares.
Ejecutar con: python merge_duplicates.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Artista, Album, Cancion
from sqlalchemy import func
from rapidfuzz import fuzz
from metadata_normalizer import normalizar_artista

UMBRAL_FUZZY = 75


def mergear_artistas():
    """Mergea artistas duplicados usando MBID, nombre_normalizado y fuzzy."""
    artistas = Artista.query.order_by(Artista.id).all()
    mergeados = 0
    procesados = set()

    # Prioridad 1: mismo musicbrainz_id
    mbid_groups = {}
    for a in artistas:
        if a.musicbrainz_id and a.id not in procesados:
            if a.musicbrainz_id not in mbid_groups:
                mbid_groups[a.musicbrainz_id] = []
            mbid_groups[a.musicbrainz_id].append(a)

    for mbid, grupo in mbid_groups.items():
        if len(grupo) < 2:
            continue
        principal = grupo[0]
        for dupe in grupo[1:]:
            if dupe.id in procesados:
                continue
            print(f"  [MBID] '{dupe.nombre}' (ID {dupe.id}) -> '{principal.nombre}' (ID {principal.id})")
            for c in Cancion.query.filter_by(artista_id=dupe.id).all():
                c.artista_id = principal.id
            for a in Album.query.filter_by(artista_id=dupe.id).all():
                a.artista_id = principal.id
            db.session.delete(dupe)
            procesados.add(dupe.id)
            mergeados += 1

    # Prioridad 2: mismo nombre_normalizado
    norm_groups = {}
    for a in artistas:
        if a.nombre_normalizado and a.id not in procesados:
            key = a.nombre_normalizado.lower().strip()
            if key not in norm_groups:
                norm_groups[key] = []
            norm_groups[key].append(a)

    for key, grupo in norm_groups.items():
        if len(grupo) < 2:
            continue
        principal = grupo[0]
        for dupe in grupo[1:]:
            if dupe.id in procesados:
                continue
            print(f"  [NORM] '{dupe.nombre}' (ID {dupe.id}) -> '{principal.nombre}' (ID {principal.id})")
            for c in Cancion.query.filter_by(artista_id=dupe.id).all():
                c.artista_id = principal.id
            for a in Album.query.filter_by(artista_id=dupe.id).all():
                a.artista_id = principal.id
            db.session.delete(dupe)
            procesados.add(dupe.id)
            mergeados += 1

    # Prioridad 3: fuzzy matching
    for i, a1 in enumerate(artistas):
        if a1.id in procesados:
            continue
        for a2 in artistas[i + 1:]:
            if a2.id in procesados:
                continue
            ratio = fuzz.token_set_ratio(a1.nombre.lower(), a2.nombre.lower())
            if ratio >= UMBRAL_FUZZY:
                principal = a1 if a1.id < a2.id else a2
                duplicado = a2 if principal.id == a1.id else a1
                print(f"  [FUZZ {ratio:.0f}] '{duplicado.nombre}' (ID {duplicado.id}) -> '{principal.nombre}' (ID {principal.id})")
                for c in Cancion.query.filter_by(artista_id=duplicado.id).all():
                    c.artista_id = principal.id
                for a in Album.query.filter_by(artista_id=duplicado.id).all():
                    a.artista_id = principal.id
                db.session.delete(duplicado)
                procesados.add(duplicado.id)
                mergeados += 1
        procesados.add(a1.id)
        if mergeados % 20 == 0 and mergeados > 0:
            db.session.commit()

    db.session.commit()
    return mergeados


def mergear_albumes_fuzzy():
    """Encuentra y mergea álbumes con nombres similares del mismo artista."""
    artistas = Artista.query.all()
    mergeados = 0

    for artista in artistas:
        albumes = Album.query.filter_by(artista_id=artista.id).order_by(Album.id).all()
        procesados = set()
        for i, al1 in enumerate(albumes):
            if al1.id in procesados:
                continue
            for al2 in albumes[i + 1:]:
                if al2.id in procesados:
                    continue
                ratio = fuzz.token_set_ratio(al1.titulo.lower(), al2.titulo.lower())
                if ratio >= UMBRAL_FUZZY:
                    principal = al1 if al1.id < al2.id else al2
                    duplicado = al2 if principal.id == al1.id else al1
                    print(f"  🔀 Álbum '{duplicado.titulo}' (ID {duplicado.id}) → '{principal.titulo}' (ID {principal.id}) (fuzzy: {ratio:.0f}%)")
                    for c in Cancion.query.filter_by(album_id=duplicado.id).all():
                        c.album_id = principal.id
                    db.session.delete(duplicado)
                    procesados.add(duplicado.id)
                    mergeados += 1
            procesados.add(al1.id)

    db.session.commit()
    return mergeados


with app.app_context():
    print("=" * 60)
    print("MERGE DE DUPLICADOS (con fuzzy matching)")
    print("=" * 60)

    print(f"\n📋 Buscando artistas duplicados (MBID + nombre_normalizado + fuzzy {UMBRAL_FUZZY}%)...")
    art_mergeados = mergear_artistas()
    print(f"✅ Artistas mergeados: {art_mergeados}")

    print(f"\n📋 Buscando álbumes duplicados (fuzzy {UMBRAL_FUZZY}%)...")
    alb_mergeados = mergear_albumes_fuzzy()
    print(f"✅ Álbumes mergeados: {alb_mergeados}")

    # Limpiar huérfanos
    huerfanos_album = 0
    for album in Album.query.all():
        if not album.canciones:
            db.session.delete(album)
            huerfanos_album += 1

    huerfanos_artista = 0
    for artista in Artista.query.all():
        if not artista.canciones and not artista.albums:
            db.session.delete(artista)
            huerfanos_artista += 1

    db.session.commit()
    print(f"\n🧹 Álbumes huérfanos eliminados: {huerfanos_album}")
    print(f"🧹 Artistas huérfanos eliminados: {huerfanos_artista}")

    print("\n" + "=" * 60)
    print("MERGE COMPLETADO")
    print("=" * 60)
