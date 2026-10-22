import unittest, time
from core import live_sources as L

class T(unittest.TestCase):
    def test_parsers_offline(self):
        f = {"opensky": {"time": 1, "states": [["a1", "X1 ", "Spain", 1, 1, 2.0, 41.0, 1000.0, False, 200.0, 90.0]]},
             "iss": {"timestamp": 1, "latitude": 1, "longitude": 2, "altitude": 420, "velocity": 27000},
             "met": {"properties": {"meta": {"updated_at": "x"}, "timeseries": [{"time": "t", "data": {"instant": {"details": {"air_temperature": 15}}}}]}},
             "kp": [{"time_tag": "t", "Kp": 2.0}]}
        for k in L.SOURCES:
            r = L.read_source(k, fetch=lambda u, k=k: f[k])
            self.assertEqual((r["tipo"], r["estado"]), ("REAL", "OK"), k)
            self.assertIn("obtenido_utc", r); self.assertIn("fuente", r)

    def test_failure_never_simulates(self):
        def boom(u): raise OSError("sin red")
        r = L.read_source("iss", fetch=boom)
        self.assertEqual(r["estado"], "PENDIENTE"); self.assertNotIn("datos", r)

    def test_snapshot_marks_e1(self):
        L._cache.clear()
        s = L.snapshot(fetch=lambda u: (_ for _ in ()).throw(OSError("x")))
        self.assertTrue(s["evidencia_deteccion"].startswith("E1"))
        L._cache.clear()

    @unittest.skipUnless(__import__("os").getenv("NNC_NET_TESTS"), "red opcional")
    def test_live_network(self):
        L._cache.clear()
        s = L.snapshot()
        self.assertTrue(any(v["estado"] == "OK" for v in s["fuentes"].values()))

if __name__ == "__main__": unittest.main()
