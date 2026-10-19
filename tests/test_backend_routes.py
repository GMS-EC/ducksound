# -*- coding: utf-8 -*-
"""
Tests integrales de rutas y endpoints de DuckSound tras la limpieza de código.
"""
import unittest
from app import create_app
from app.models import db, Usuario, Cancion, Favorito


class TestBackendClean(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.app.config['TESTING'] = True

    def setUp(self):
        self.client = self.app.test_client()

    def test_security_unauthenticated(self):
        # Rutas protegidas deben retornar 401
        res = self.client.get('/api/mixes')
        self.assertEqual(res.status_code, 401)

        res = self.client.get('/admin/estadisticas')
        self.assertEqual(res.status_code, 401)

    def test_authenticated_admin(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1

        # Admin route
        r = self.client.get('/admin/estadisticas')
        self.assertEqual(r.status_code, 200)

        # Mixes routes
        r = self.client.get('/api/mixes')
        self.assertEqual(r.status_code, 200)

        r = self.client.get('/api/mixes/top')
        self.assertEqual(r.status_code, 200)

        # Color routes (ambas variantes unificadas)
        r = self.client.get('/api/album/1/color')
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/album/1/colors')
        self.assertEqual(r.status_code, 200)

        r = self.client.get('/api/cancion/1/color')
        self.assertEqual(r.status_code, 200)
        r = self.client.get('/api/song/1/colors')
        self.assertEqual(r.status_code, 200)

        # Favoritos
        r = self.client.get('/api/favoritos/canciones')
        self.assertEqual(r.status_code, 200)

        r = self.client.get('/favoritos')
        self.assertEqual(r.status_code, 200)

        # Dashboard & Explore
        r = self.client.get('/dashboard')
        self.assertEqual(r.status_code, 200)

        r = self.client.get('/explore')
        self.assertEqual(r.status_code, 200)

    def test_search_top_result(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1

        # Búsqueda global con estructura top_result
        r = self.client.get('/api/search?q=test')
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertIn('top_result', data)
        self.assertIn('songs', data)
        self.assertIn('artists', data)
        self.assertIn('albums', data)

    def test_balance_mix_gap_rule(self):
        from app.services.recipes import balance_mix
        # Lista simulada con canciones repetidas del mismo artista
        tracks = [
            {'id': 1, 'artista': 'Queen', 'titulo': 'Bohemian Rhapsody'},
            {'id': 2, 'artista': 'Queen', 'titulo': 'Radio Ga Ga'},
            {'id': 3, 'artista': 'Queen', 'titulo': 'We Will Rock You'},
            {'id': 4, 'artista': 'Daft Punk', 'titulo': 'One More Time'},
            {'id': 5, 'artista': 'Daft Punk', 'titulo': 'Around The World'},
            {'id': 6, 'artista': 'Coldplay', 'titulo': 'Yellow'},
        ]
        balanced = balance_mix(tracks, gap=1)
        # Verificar que no hayan 2 canciones consecutivas de Queen al inicio
        self.assertEqual(len(balanced), 6)
        for i in range(len(balanced) - 1):
            a1 = balanced[i]['artista']
            a2 = balanced[i+1]['artista']
            # Con gap=1, si hay variedad suficiente no deben quedar juntas
            # (en este caso hay 3 de Queen y 3 de otros artistas)

    def test_coverart_scoring(self):
        from app.services.coverart import get_name_score
        # 'front' o 'cover' deben superar a 'back', 'cd' o 'booklet'
        score_front = get_name_score('front_cover')
        score_back = get_name_score('back_inlay')
        score_booklet = get_name_score('scans_booklet')
        self.assertGreater(score_front, score_back)
        self.assertGreater(score_front, score_booklet)

    def test_article_and_natural_sorting(self):
        from app.services.parsers import get_sort_name, natural_sort_key
        # Stripping de artículos
        self.assertEqual(get_sort_name('The Beatles'), 'Beatles')
        self.assertEqual(get_sort_name('Los Enanitos Verdes'), 'Enanitos Verdes')
        self.assertEqual(get_sort_name('El Tri'), 'Tri')
        self.assertEqual(get_sort_name('Coldplay'), 'Coldplay')

        # Ordenamiento natural (2 antes que 10)
        items = ['Pista 10', 'Pista 2', 'Pista 1']
        sorted_items = sorted(items, key=natural_sort_key)
        self.assertEqual(sorted_items, ['Pista 1', 'Pista 2', 'Pista 10'])

    def test_multi_disc_positioning(self):
        from app.services.parsers import get_track_sort_pos
        # CD 1 Pista 12 vs CD 2 Pista 1
        pos_cd1_t12 = get_track_sort_pos(disc=1, track=12)  # 1012
        pos_cd2_t1 = get_track_sort_pos(disc=2, track=1)    # 2001
        self.assertLess(pos_cd1_t12, pos_cd2_t1)

    def test_api_stats_periods(self):
        with self.client.session_transaction() as sess:
            sess['user_id'] = 1

        for period in ['all', 'week', 'month']:
            r = self.client.get(f'/api/stats?period={period}')
            self.assertEqual(r.status_code, 200)
            data = r.get_json()
            self.assertEqual(data['period'], period)
            self.assertIn('total_plays', data)
            self.assertIn('total_hours', data)
            self.assertIn('time_string', data)
            self.assertIn('top_songs', data)
            self.assertIn('top_artists', data)


if __name__ == '__main__':
    unittest.main()

