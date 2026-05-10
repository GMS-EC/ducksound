"""
Tests del módulo recommender (get_similar_songs).
Requiere base de datos — se marcan como skip si no hay contexto de app.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
from recommender import get_similar_songs


class TestRecommender:

    def test_module_imports(self):
        """Verifica que el módulo recommender se importa correctamente."""
        from recommender import get_similar_songs
        assert callable(get_similar_songs)

    @pytest.mark.skip(reason="Requiere base de datos con Flask app context")
    def test_empty_for_missing_song(self):
        result = get_similar_songs(-1, top_k=5)
        assert result == []

    @pytest.mark.skip(reason="Requiere base de datos con Flask app context")
    def test_result_structure(self):
        result = get_similar_songs(1, top_k=5)
        if result:
            r = result[0]
            assert 'id' in r
            assert 'titulo' in r
            assert 'artista' in r
            assert 'similarity' in r
            assert 0 <= r['similarity'] <= 1
