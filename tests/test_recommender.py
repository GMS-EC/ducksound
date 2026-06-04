# -*- coding: utf-8 -*-
"""
Tests del módulo recommender (get_similar_songs) usando unittest.
"""
import sys
import os
import unittest

# Añadir directorio raíz al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.recommender import get_similar_songs


class TestRecommender(unittest.TestCase):

    def test_module_imports(self):
        """Verifica que el módulo recommender se importa correctamente y es callable."""
        self.assertTrue(callable(get_similar_songs))

    def test_empty_for_missing_song(self):
        try:
            from flask import current_app
            if not current_app:
                self.skipTest("Requiere base de datos con Flask app context")
        except (ImportError, RuntimeError):
            self.skipTest("Requiere base de datos con Flask app context")
            
        result = get_similar_songs(-1, top_k=5)
        self.assertEqual(result, [])

    def test_result_structure(self):
        try:
            from flask import current_app
            if not current_app:
                self.skipTest("Requiere base de datos con Flask app context")
        except (ImportError, RuntimeError):
            self.skipTest("Requiere base de datos con Flask app context")
            
        result = get_similar_songs(1, top_k=5)
        if result:
            r = result[0]
            self.assertIn('id', r)
            self.assertIn('titulo', r)
            self.assertIn('artista', r)
            self.assertIn('similarity', r)
            self.assertTrue(0 <= r['similarity'] <= 1)


if __name__ == '__main__':
    unittest.main()
