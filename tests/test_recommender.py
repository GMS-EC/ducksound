"""
Tests del módulo recommender (get_similar_songs).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from recommender import get_similar_songs


class TestRecommender:
    def test_empty_for_missing_song(self):
        """Si la canción no existe, debe devolver lista vacía."""
        result = get_similar_songs(-1, top_k=5)
        assert result == []

    def test_result_structure(self):
        """Los resultados deben tener los campos esperados."""
        result = get_similar_songs(1, top_k=5)
        if result:
            r = result[0]
            assert 'id' in r
            assert 'titulo' in r
            assert 'artista' in r
            assert 'similarity' in r
            assert 0 <= r['similarity'] <= 1
