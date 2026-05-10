#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script para mergear artistas y álbumes duplicados existentes en la BD.
Ejecutar con: python merge_duplicates.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import app
from models import db, Artista, Album, Cancion
from sqlalchemy import func, text

with app.app_context():
    print("=" * 60)
    print("MERGE DE DUPLICADOS")
    print("=" * 60)
    
    # === 1. MERGEAR ARTISTAS DUPLICADOS ===
    print("\n📋 Buscando artistas duplicados...")
    
    # Encontrar artistas con mismo nombre normalizado (LOWER(TRIM))
    duplicados = db.session.query(
        func.lower(func.trim(Artista.nombre)).label('nombre_norm'),
        func.count(Artista.id).label('cnt'),
        func.min(Artista.id).label('min_id')
    ).group_by(
        func.lower(func.trim(Artista.nombre))
    ).having(func.count(Artista.id) > 1).all()
    
    artistas_mergeados = 0
    for dup in duplicados:
        nombre_norm = dup[0]
        artistas = Artista.query.filter(
            func.lower(func.trim(Artista.nombre)) == nombre_norm
        ).order_by(Artista.id).all()
        
        if len(artistas) < 2:
            continue
        
        principal = artistas[0]  # El primero (más antiguo) es el principal
        for dupe in artistas[1:]:
            print(f"  🔀 Mergeando '{dupe.nombre}' (ID {dupe.id}) → '{principal.nombre}' (ID {principal.id})")
            
            # Migrar canciones del duplicado al principal
            canciones = Cancion.query.filter_by(artista_id=dupe.id).all()
            for c in canciones:
                c.artista_id = principal.id
                print(f"     Canción '{c.titulo}' reasignada")
            
            # Migrar álbumes del duplicado al principal
            albumes = Album.query.filter_by(artista_id=dupe.id).all()
            for a in albumes:
                a.artista_id = principal.id
                print(f"     Álbum '{a.titulo}' reasignado")
            
            # Eliminar el artista duplicado
            db.session.delete(dupe)
            artistas_mergeados += 1
        
        db.session.commit()
    
    print(f"✅ Artistas mergeados: {artistas_mergeados}")
    
    # === 2. MERGEAR ÁLBUMES DUPLICADOS ===
    print("\n📋 Buscando álbumes duplicados...")
    
    albumes_duplicados = db.session.query(
        func.lower(func.trim(Album.titulo)).label('titulo_norm'),
        Album.artista_id,
        func.count(Album.id).label('cnt'),
        func.min(Album.id).label('min_id')
    ).group_by(
        func.lower(func.trim(Album.titulo)),
        Album.artista_id
    ).having(func.count(Album.id) > 1).all()
    
    albumes_mergeados = 0
    for dup in albumes_duplicados:
        titulo_norm = dup[0]
        artista_id = dup[1]
        
        albumes = Album.query.filter(
            func.lower(func.trim(Album.titulo)) == titulo_norm,
            Album.artista_id == artista_id
        ).order_by(Album.id).all()
        
        if len(albumes) < 2:
            continue
        
        principal = albumes[0]
        for dupe in albumes[1:]:
            print(f"  🔀 Mergeando álbum '{dupe.titulo}' (ID {dupe.id}) → '{principal.titulo}' (ID {principal.id})")
            
            canciones = Cancion.query.filter_by(album_id=dupe.id).all()
            for c in canciones:
                c.album_id = principal.id
                print(f"     Canción '{c.titulo}' reasignada")
            
            db.session.delete(dupe)
            albumes_mergeados += 1
        
        db.session.commit()
    
    print(f"✅ Álbumes mergeados: {albumes_mergeados}")
    
    # === 3. LIMPIAR HUÉRFANOS ===
    print("\n📋 Limpiando huérfanos...")
    
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
    print(f"✅ Álbumes huérfanos eliminados: {huerfanos_album}")
    print(f"✅ Artistas huérfanos eliminados: {huerfanos_artista}")
    
    print("\n" + "=" * 60)
    print("MERGE COMPLETADO")
    print("=" * 60)
