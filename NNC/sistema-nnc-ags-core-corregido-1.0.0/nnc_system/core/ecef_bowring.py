import math
A = 6378137.0
F = 1.0 / 298.257223563
B = A * (1.0 - F)
E2 = F * (2.0 - F)
E2_PRIME = (A**2 - B**2) / (B**2)

def ecef_to_lla(x, y, z):
    p = math.sqrt(x**2 + y**2)
    lon_rad = math.atan2(y, x)
    if p < 1e-6:
        lat_rad = math.pi / 2.0 if z >= 0 else -math.pi / 2.0
        return math.degrees(lat_rad), math.degrees(lon_rad), abs(z) - B
    theta = math.atan2(z * A, p * B)
    lat_rad = math.atan2(z + E2_PRIME * B * (math.sin(theta)**3), p - E2 * A * (math.cos(theta)**3))
    n = A / math.sqrt(1.0 - E2 * (math.sin(lat_rad)**2))
    h = (p / math.cos(lat_rad)) - n
    return math.degrees(lat_rad), math.degrees(lon_rad), h

def validar_ingreso_ecef(x, y, z):
    lat, lon, h = ecef_to_lla(x, y, z)
    if h < 0:
        return False, 'RECHAZADO_INGRESO', f'Altitud bajo elipsoide WGS84 ({h:.2f} m)'
    return True, 'ADMITIDO', f'Coordenada valida (h = {h:.2f} m)'
