# -*- coding: utf-8 -*-
"""ALLEN IVERSON (harness/track_kunye/allen_iverson.py).

GÖREVİ: Frame Bindirme & Temporal Super-Frame Composite Generator.
Kullanıcının 'Frame Bindirme' stratejisi:
  Grup/küme içindeki kareleri üst üste bindirir, arka plan gürültüsünü
  medyan/min filtreleri ile temizler ve harfleri %100 kristalize eden
  'Super-Kare' (Super Frame) görselini üretir.

NOT: Bu modül saklanmış bir bağımsız motor bileşenidir (aktife entegre edilmemiştir).
"""
import cv2
import numpy as np
from pathlib import Path


def uret_super_kare(grup_griler: list[np.ndarray], yontem: str = "medyan") -> np.ndarray:
    """Grup içindeki kareleri üst üste bindirir ve ortak/sabit pikselleri bırakır.
    
    yontem='min'    -> Sadece tüm karelerde ortak olan EN DÜŞÜK pikseli alır. (Agresif Temizlik)
    yontem='medyan' -> Piksellerin medyanını alır. (Gürültü siler, kenarı korur, Türkçe harfleri onarır)
    """
    if not grup_griler:
        raise ValueError("grup_griler listesi boş olamaz.")
    
    if len(grup_griler) == 1:
        return grup_griler[0]
    
    # Güvenlik: Tüm karelerin boyutu aynı olmalı
    h_min = min(g.shape[0] for g in grup_griler)
    w_min = min(g.shape[1] for g in grup_griler)
    kesilmis = [g[:h_min, :w_min] for g in grup_griler]
    
    # Matrisleri 3. boyutta (Z ekseni) üst üste istifler
    stack = np.stack(kesilmis, axis=0)
    
    if yontem == "min":
        return np.min(stack, axis=0).astype(np.uint8)
    else:
        return np.median(stack, axis=0).astype(np.uint8)


def generate_super_frame_from_files(image_paths: list[Path | str], output_path: Path | str = None, yontem: str = "medyan") -> np.ndarray:
    """Dosya yolları verilen görsellerden Super-Kare üretir ve isteğe bağlı kaydeder."""
    images = []
    for p in image_paths:
        p_str = str(p)
        img = cv2.imread(p_str)
        if img is None:
            # Unicode path fallback
            img = cv2.imdecode(np.fromfile(p_str, dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is not None:
            images.append(img)
            
    if not images:
        raise FileNotFoundError("Hiçbir resim okunamadı.")
        
    super_frame = uret_super_kare(images, yontem=yontem)
    
    if output_path:
        out_p = str(output_path)
        ext = Path(out_p).suffix or ".png"
        is_success, buffer = cv2.imencode(ext, super_frame)
        if is_success:
            buffer.tofile(out_p)
            
    return super_frame
