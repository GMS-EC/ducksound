# -*- coding: utf-8 -*-
"""
Tests de normalización de artistas usando unittest.
"""
import sys
import os
import unittest

# Añadir directorio raíz al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.metadata import normalizar_artista


class TestNormalizarArtista(unittest.TestCase):
    def test_feat_removal(self):
        self.assertEqual(normalizar_artista("Artist A feat. Artist B"), "Artist A")
        self.assertEqual(normalizar_artista("Artist A ft. Artist B"), "Artist A")
        self.assertEqual(normalizar_artista("Artist A featuring Artist B"), "Artist A")

    def test_ampersand(self):
        self.assertEqual(normalizar_artista("Artist A & Artist B"), "Artist A")

    def test_and_lowercase_collaboration(self):
        self.assertEqual(normalizar_artista("artist a and artist b"), "artist a")

    def test_and_uppercase_preserved(self):
        self.assertEqual(normalizar_artista("Blade And Bath"), "Blade And Bath")

    def test_comma_delimiter(self):
        self.assertEqual(normalizar_artista("Artist A, Artist B"), "Artist A")

    def test_slash_delimiter(self):
        self.assertEqual(normalizar_artista("Artist A / Artist B"), "Artist A")
        self.assertEqual(normalizar_artista("Blade and Bath/ Decalius"), "Blade and Bath")

    def test_acdc_preserved(self):
        self.assertEqual(normalizar_artista("AC/DC"), "AC/DC")

    def test_the_unification(self):
        self.assertEqual(normalizar_artista("Smith, The"), "The Smith")

    def test_ghost_bc(self):
        self.assertEqual(normalizar_artista("Ghost B.C."), "Ghost")

    def test_vs_delimiter(self):
        self.assertEqual(normalizar_artista("Artist A vs Artist B"), "Artist A")

    def test_plus_delimiter(self):
        self.assertEqual(normalizar_artista("Artist A + Artist B"), "Artist A")

    def test_x_delimiter(self):
        self.assertEqual(normalizar_artista("Artist A x Artist B"), "Artist A")

    def test_none_and_empty(self):
        self.assertIsNone(normalizar_artista(None))
        self.assertEqual(normalizar_artista(""), "")


if __name__ == '__main__':
    unittest.main()
