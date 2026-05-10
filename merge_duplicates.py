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

UMBRAL_FUZZY = 82  # Porcentaje mínimo para considerar duplicado


def mergear_artistas_fuzzy():
    """Encuentra y mergea artistas con nombres similares vía fuzzy matching."""
    artistas = Artista.query.order_by(Artista.id).all()
    mergeados = 0
    procesados = set()

    for i, a1 in enumerate(artistas):
        if a1.id in procesados:
            continue
        for a2 in artistas[i + 1:]:
            if a2.id in procesados:
                continue
            ratio = fuzz.ratio(a1.nombre.lower(), a2.nombre.lower())
            if ratio >= UMBRAL_FUZZY:
                principal = a1 if a1.id < a2.id else a2
                duplicado = a2 if principal.id == a1.id else a1
                print(f"  🔀 '{duplicado.nombre}' (ID {duplicado.id}) → '{principal.nombre}' (ID {principal.id}) (fuzzy: {ratio:.0f}%)")
                for c in Cancion.query.filter_by(artista_id=duplicado.id).all():
                    c.artista_id = principal.id
                for a in Album.query.filter_by(artista_id=duplicado.id).all():
                    a.artista_id = principal.id
                db.session.delete(duplicado)
                procesados.add(duplicado.id)
                mergeados += 1
        procesados.add(a1.id)
        if mergeados % 10 == 0 and mergeados > 0:
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
                ratio = fuzz.ratio(al1.titulo.lower(), al2.titulo.lower())
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

    print(f"\n📋 Buscando artistas duplicados (umbral: {UMBRAL_FUZZY}%)...")
    art_mergeados = mergear_artistas_fuzzy()
    print(f"✅ Artistas mergeados: {art_mergeados}")

    print(f"\n📋 Buscando álbumes duplicados (umbral: {UMBRAL_FUZZY}%)...")
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
