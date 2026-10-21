import numpy as np
import math

class ExtendedKalmanFilter3D:
    """
    Filtro de Kalman Extendido (EKF 3D) de 9 estados:
    Estado X = [x, y, z, vx, vy, vz, ax, ay, az]^T
    Permite estimar posición, velocidad y aceleración inercial continua.
    """
    def __init__(self, dt=0.1, std_process=1.0, std_measure=5.0):
        self.dt = dt
        self.dim_x = 9
        self.dim_z = 3
        
        # Estado inicial [x, y, z, vx, vy, vz, ax, ay, az]
        self.x = np.zeros((9, 1))
        self.initialized = False
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt debe ser positivo y finito")
        if std_process < 0 or std_measure <= 0:
            raise ValueError("Las desviaciones típicas deben ser válidas")
        
        # Matriz de covarianza del estado P
        self.P = np.eye(9) * 1000.0
        
        # Matriz de transición de estado F
        self.F = np.eye(9)
        for i in range(3):
            self.F[i, i+3] = dt
            self.F[i, i+6] = 0.5 * (dt**2)
            self.F[i+3, i+6] = dt
            
        # Matriz de observación H (medimos x, y, z)
        self.H = np.zeros((3, 9))
        self.H[0, 0] = 1.0
        self.H[1, 1] = 1.0
        self.H[2, 2] = 1.0
        
        # Ruido de proceso Q y Ruido de medida R
        self.std_measure = float(std_measure)
        self.Q = np.eye(9) * (std_process**2)
        self.R = np.eye(3) * (std_measure**2)

    def predict(self):
        self.x = self.F @ self.x
        self.P = self.F @ self.P @ self.F.T + self.Q
        return self.x

    def update(self, z_meas):
        z_meas = np.asarray(z_meas, dtype=float).reshape((3, 1))
        if not np.all(np.isfinite(z_meas)):
            raise ValueError("La medición debe contener valores finitos")
        if not self.initialized:
            self.x[:3, :] = z_meas
            self.P[:3, :3] = np.eye(3) * (self.std_measure ** 2 if hasattr(self, "std_measure") else 25.0)
            self.initialized = True
            return self.x.copy(), 0.0
        y = z_meas - (self.H @ self.x)  # Innovación
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)  # Ganancia de Kalman
        
        self.x = self.x + (K @ y)
        I = np.eye(self.dim_x)
        # Forma de Joseph: conserva mejor simetría/semidefinición positiva.
        A = I - K @ self.H
        self.P = A @ self.P @ A.T + K @ self.R @ K.T
        self.P = (self.P + self.P.T) / 2.0
        return self.x.copy(), float(np.linalg.norm(y))


def corregir_refraccion_atmosferica(el_deg, h_m, temp_c=15.0, press_hpa=1013.25):
    """
    Modelo de refracción atmosférica troposférica (Bennett/Saastamoinen)
    Corrige el ángulo de elevación óptico por efecto de la densidad del aire en costa/mar.
    """
    if el_deg < 0.5:
        # Refracción cerca del horizonte marino
        R_arcmin = 1.0 / math.tan(math.radians(el_deg + 7.31 / (el_deg + 4.4)))
    else:
        R_arcmin = 1.0 / math.tan(math.radians(el_deg + 10.3 / (el_deg + 5.11)))
        
    # Corrección por presión y temperatura
    factor_pt = (press_hpa / 1013.25) * (283.15 / (273.15 + temp_c))
    R_deg = (R_arcmin / 60.0) * factor_pt
    el_corregido = el_deg - R_deg
    return max(0.0, el_corregido), R_deg


def calcular_entropia_cinematica(vector_velocidades):
    """
    Calcula la entropía de Shannon (H) del perfil de velocidad.
    Una baja entropía indica trayectoria uniforme/balística.
    Una alta entropía cuantifica maniobras impredecibles y aceleraciones no convencionales.
    """
    if len(vector_velocidades) == 0:
        return 0.0
    values = np.asarray(vector_velocidades, dtype=float)
    values = values[np.isfinite(values)]
    if values.size == 0:
        return 0.0
    counts, _ = np.histogram(values, bins=min(10, max(1, values.size)))
    probabilities = counts[counts > 0].astype(float) / counts.sum()
    return float(-np.sum(probabilities * np.log2(probabilities)))


def verificar_crc16(data_bytes):
    """
    Verificación de integridad de trama sensorial mediante CRC-16-CCITT.
    """
    crc = 0xFFFF
    for b in data_bytes:
        crc ^= (b << 8)
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


def hamming_7_4_encode(data_4bit):
    """
    Codificación Hamming(7,4) para corrección de errores en telemetría de 1 bit.
    data_4bit: entero de 0 a 15
    """
    d0 = (data_4bit >> 3) & 1
    d1 = (data_4bit >> 2) & 1
    d2 = (data_4bit >> 1) & 1
    d3 = data_4bit & 1
    
    p0 = d0 ^ d1 ^ d2
    p1 = d1 ^ d2 ^ d3
    p2 = d0 ^ d1 ^ d3
    
    code = (p0 << 6) | (p1 << 5) | (d0 << 4) | (p2 << 3) | (d1 << 2) | (d2 << 1) | d3
    return code
