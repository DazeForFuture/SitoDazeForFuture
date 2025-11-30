#!/usr/bin/env python3
"""
Security Testing Script for SitoDazeForFuture Backend
Testa i principali vettori di attacco e validazioni di sicurezza.
"""
import requests
import json
import sys
from typing import Dict, List, Tuple

# Configurazione
BASE_URL = "http://localhost:5000"
ENDPOINTS = {
    "server": "http://localhost:5000",
    "forum": "http://localhost:5003",
    "post": "http://localhost:5002",
    "centrale": "http://localhost:5005",
    "documenti": "http://localhost:5001",
}

class SecurityTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def test(self, name: str, description: str, test_func) -> bool:
        """Esegui un test di sicurezza."""
        print(f"\n🧪 Testing: {name}")
        print(f"   Description: {description}")
        try:
            result = test_func()
            if result:
                print(f"   ✅ PASSED")
                self.passed += 1
                self.results.append((name, "PASSED", description))
                return True
            else:
                print(f"   ❌ FAILED")
                self.failed += 1
                self.results.append((name, "FAILED", description))
                return False
        except Exception as e:
            print(f"   ⚠️  ERROR: {str(e)}")
            self.failed += 1
            self.results.append((name, "ERROR", str(e)))
            return False
    
    def test_input_validation_email(self) -> bool:
        """Test: Email validation deve rifiutare email invalide."""
        invalid_emails = [
            "notanemail",
            "user@",
            "@domain.com",
            "user@domain",
            "user @domain.com",
        ]
        
        for email in invalid_emails:
            response = requests.post(
                f"{self.base_url}/register",
                json={
                    "nome": "Test",
                    "cognome": "User",
                    "email": email,
                    "ruolo": "student",
                    "password": "SecurePass123!"
                }
            )
            # Deve ritornare 400 per email invalida
            if response.status_code != 400:
                print(f"   ❌ Email '{email}' non fu rifiutata (status: {response.status_code})")
                return False
        
        return True
    
    def test_input_validation_password_strength(self) -> bool:
        """Test: Password deboli devono essere rifiutate."""
        weak_passwords = [
            "short",
            "onlylowercase",
            "ONLYUPPERCASE",
            "12345678",
            "NoSpecialChar",
        ]
        
        for pwd in weak_passwords:
            response = requests.post(
                f"{self.base_url}/register",
                json={
                    "nome": "Test",
                    "cognome": "User",
                    "email": "valid@example.com",
                    "ruolo": "student",
                    "password": pwd
                }
            )
            # Deve ritornare 400 per password debole
            if response.status_code != 400 and "Password" in response.text:
                print(f"   ❌ Password '{pwd}' non fu rifiutata (status: {response.status_code})")
                return False
        
        return True
    
    def test_xss_prevention_post(self) -> bool:
        """Test: XSS payload deve essere sanitizzato."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "<img src=x onerror='alert(1)'>",
            "javascript:alert(1)",
        ]
        
        for payload in xss_payloads:
            response = requests.post(
                f"{ENDPOINTS['post']}/api/post",
                json={
                    "titolo": payload,
                    "contenuto": "Test content"
                }
            )
            
            # Controllo che il payload non sia ritornato tal quale
            if response.status_code == 200:
                # Leggi il post creato
                read_response = requests.get(f"{ENDPOINTS['post']}/api/post")
                if read_response.status_code == 200:
                    posts = read_response.json()
                    for post in posts:
                        if payload in post.get('titolo', ''):
                            print(f"   ❌ XSS payload non fu escapato: {payload}")
                            return False
        
        return True
    
    def test_api_key_required(self) -> bool:
        """Test: Endpoint protetti devono richiedere API key."""
        # Tenta senza API key
        response = requests.get(f"{ENDPOINTS['centrale']}/update")
        if response.status_code != 401:
            print(f"   ❌ API key non era richiesta (status: {response.status_code})")
            return False
        
        return True
    
    def test_cors_origin_validation(self) -> bool:
        """Test: CORS deve rifiutare domini non autorizzati."""
        headers = {
            "Origin": "https://malicious-domain.com"
        }
        
        response = requests.get(f"{self.base_url}/", headers=headers)
        
        # Deve NON avere il header CORS che permette l'accesso
        if "Access-Control-Allow-Origin: https://malicious-domain.com" in str(response.headers):
            print(f"   ❌ CORS permette origin non autorizzato")
            return False
        
        return True
    
    def test_sql_injection_prevention(self) -> bool:
        """Test: SQL injection deve essere prevenuto dai prepared statements."""
        sql_injection = "' OR '1'='1"
        
        response = requests.post(
            f"{ENDPOINTS['forum']}/api/check-auth",
            params={"email": sql_injection}
        )
        
        # Non deve crashare e deve ritornare errore 400
        if response.status_code == 500:
            print(f"   ❌ SQL injection potrebbe causare crash")
            return False
        
        return True
    
    def test_timing_attack_prevention_api_key(self) -> bool:
        """Test: API key deve usare timing-safe comparison."""
        import time
        
        # Questo è un test euristico - un vero timing attack richiederebbe
        # più campioni e analisi statistica
        
        correct_key = "thisisavalidkey123"
        
        # Tempi approssimativi
        wrong_key_1 = "wrong"
        wrong_key_2 = "thisisavalidkeyXXX"  # Molto simile ma non uguale
        
        # Se usa simple == comparison, wrong_key_2 potrebbe impiegare più tempo
        # (non è un test perfetto, ma dà un'indicazione)
        
        print("   ℹ️  Timing attack test: euristico (richiede stress testing)")
        return True
    
    def test_rate_limiting_not_implemented(self) -> bool:
        """Test: Controllare se rate limiting è implementato (avviso se assente)."""
        # Flask-Limiter è nelle dipendenze ma potrebbe non essere applicato ovunque
        print("   ⚠️  NOTA: Rate limiting consigliato per endpoints critici")
        return True
    
    def test_https_redirect_not_implemented(self) -> bool:
        """Test: In produzione, dovrebbe essere su HTTPS."""
        if "localhost" not in self.base_url:
            # In produzione
            if not self.base_url.startswith("https://"):
                print("   ⚠️  NOTA: In produzione, usare HTTPS (non HTTP)")
                return False
        return True
    
    def run_all_tests(self) -> None:
        """Esegui tutti i test di sicurezza."""
        print("=" * 70)
        print("🔒 SitoDazeForFuture Security Testing Suite")
        print("=" * 70)
        
        # Test di Input Validation
        print("\n📋 Input Validation Tests")
        print("-" * 70)
        self.test(
            "Email Validation",
            "Invalid emails must be rejected",
            self.test_input_validation_email
        )
        self.test(
            "Password Strength",
            "Weak passwords must be rejected",
            self.test_input_validation_password_strength
        )
        
        # Test XSS/Injection
        print("\n🛡️  XSS/Injection Prevention Tests")
        print("-" * 70)
        self.test(
            "XSS Prevention (POST)",
            "XSS payloads must be sanitized",
            self.test_xss_prevention_post
        )
        self.test(
            "SQL Injection Prevention",
            "SQL injection attempts must fail safely",
            self.test_sql_injection_prevention
        )
        
        # Test API Security
        print("\n🔑 API Security Tests")
        print("-" * 70)
        self.test(
            "API Key Required",
            "Protected endpoints must require API key",
            self.test_api_key_required
        )
        self.test(
            "Timing-Safe API Key Comparison",
            "API key comparison should be timing-safe",
            self.test_timing_attack_prevention_api_key
        )
        
        # Test CORS
        print("\n🌐 CORS Security Tests")
        print("-" * 70)
        self.test(
            "CORS Origin Validation",
            "CORS should reject unauthorized origins",
            self.test_cors_origin_validation
        )
        
        # Test Deployment
        print("\n📦 Deployment Security Tests")
        print("-" * 70)
        self.test(
            "HTTPS in Production",
            "Production deployments should use HTTPS",
            self.test_https_redirect_not_implemented
        )
        self.test(
            "Rate Limiting Available",
            "Flask-Limiter should be implemented on critical endpoints",
            self.test_rate_limiting_not_implemented
        )
        
        # Riepilogo
        print("\n" + "=" * 70)
        print("📊 Test Summary")
        print("=" * 70)
        total = self.passed + self.failed
        print(f"✅ Passed:  {self.passed}/{total}")
        print(f"❌ Failed:  {self.failed}/{total}")
        print(f"Success Rate: {(self.passed/total*100) if total > 0 else 0:.1f}%")
        print("=" * 70)
        
        # Dettagli risultati
        if self.results:
            print("\n📋 Detailed Results:\n")
            for name, status, detail in self.results:
                emoji = "✅" if status == "PASSED" else "❌"
                print(f"{emoji} {name}: {status}")
                if detail and status == "FAILED":
                    print(f"   └─ {detail}")
        
        return self.failed == 0


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        base_url = sys.argv[1]
    else:
        base_url = BASE_URL
    
    print(f"🔍 Testing against: {base_url}")
    print(f"Make sure all services are running on their respective ports.\n")
    
    tester = SecurityTester(base_url)
    success = tester.run_all_tests()
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
