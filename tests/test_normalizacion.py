"""
Tests de normalización de artistas.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from metadata_normalizer import normalizar_artista


class TestNormalizarArtista:
    def test_feat_removal(self):
        assert normalizar_artista("Artist A feat. Artist B") == "Artist A"
        assert normalizar_artista("Artist A ft. Artist B") == "Artist A"
        assert normalizar_artista("Artist A featuring Artist B") == "Artist A"

    def test_ampersand(self):
        assert normalizar_artista("Artist A & Artist B") == "Artist A"

    def test_and_lowercase_collaboration(self):
        assert normalizar_artista("artist a and artist b") == "artist a"

    def test_and_uppercase_preserved(self):
        assert normalizar_artista("Blade And Bath") == "Blade And Bath"

    def test_comma_delimiter(self):
        assert normalizar_artista("Artist A, Artist B") == "Artist A"

    def test_slash_delimiter(self):
        assert normalizar_artista("Artist A / Artist B") == "Artist A"
        assert normalizar_artista("Blade and Bath/ Decalius") == "Blade and Bath"

    def test_acdc_preserved(self):
        assert normalizar_artista("AC/DC") == "AC/DC"

    def test_the_unification(self):
        assert normalizar_artista("Smith, The") == "The Smith"

    def test_ghost_bc(self):
        assert normalizar_artista("Ghost B.C.") == "Ghost"

    def test_vs_delimiter(self):
        assert normalizar_artista("Artist A vs Artist B") == "Artist A"

    def test_plus_delimiter(self):
        assert normalizar_artista("Artist A + Artist B") == "Artist A"

    def test_x_delimiter(self):
        assert normalizar_artista("Artist A x Artist B") == "Artist A"

    def test_none_and_empty(self):
        assert normalizar_artista(None) is None
        assert normalizar_artista("") == ""
