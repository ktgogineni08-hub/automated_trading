#!/usr/bin/env python3
"""
Comprehensive tests for data_encryption.py module
Tests DataEncryptor and SecureArchiveManager for security
"""

import pytest
import tempfile
import shutil
import json
from pathlib import Path
import sys
import os

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.data_encryption import (
    EncryptionMetadata,
    DataEncryptor,
    SecureArchiveManager,
    get_global_encryptor
)


# Test password
TEST_PASSWORD = "TestSecurePassword123!@#"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def temp_dir():
    """Create temporary directory for tests"""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    # Cleanup
    if temp_path.exists():
        shutil.rmtree(temp_path)


@pytest.fixture
def encryptor():
    """Create DataEncryptor with test password"""
    return DataEncryptor(master_password=TEST_PASSWORD)


@pytest.fixture
def archive_manager(temp_dir):
    """Create SecureArchiveManager with test password"""
    return SecureArchiveManager(
        archive_dir=temp_dir / "archives",
        master_password=TEST_PASSWORD
    )


# ============================================================================
# EncryptionMetadata Tests
# ============================================================================

class TestEncryptionMetadata:
    """Test EncryptionMetadata dataclass"""

    def test_metadata_default_values(self):
        """Test metadata with default values"""
        metadata = EncryptionMetadata()
        
        assert metadata.version == "1.0"
        assert metadata.algorithm == "AES-256-GCM"
        assert metadata.key_derivation == "PBKDF2-SHA256"
        assert metadata.iterations == 100_000
        assert metadata.compressed is False

    def test_metadata_custom_values(self):
        """Test metadata with custom values"""
        metadata = EncryptionMetadata(
            version="2.0",
            algorithm="AES-128-GCM",
            compressed=True,
            iterations=200_000
        )
        
        assert metadata.version == "2.0"
        assert metadata.algorithm == "AES-128-GCM"
        assert metadata.compressed is True
        assert metadata.iterations == 200_000

    def test_metadata_to_dict(self):
        """Test converting metadata to dictionary"""
        metadata = EncryptionMetadata(created_at="2025-01-01T00:00:00")
        result = metadata.to_dict()
        
        assert isinstance(result, dict)
        assert result['version'] == "1.0"
        assert result['algorithm'] == "AES-256-GCM"
        assert result['created_at'] == "2025-01-01T00:00:00"

    def test_metadata_from_dict(self):
        """Test creating metadata from dictionary"""
        data = {
            'version': '1.0',
            'algorithm': 'AES-256-GCM',
            'created_at': '2025-01-01T00:00:00',
            'key_derivation': 'PBKDF2-SHA256',
            'iterations': 100_000,
            'compressed': True
        }
        
        metadata = EncryptionMetadata.from_dict(data)
        
        assert metadata.version == "1.0"
        assert metadata.compressed is True


# ============================================================================
# DataEncryptor Initialization Tests
# ============================================================================

class TestDataEncryptorInitialization:
    """Test DataEncryptor initialization"""

    def test_initialization_with_password(self):
        """Test initialization with provided password"""
        encryptor = DataEncryptor(master_password=TEST_PASSWORD)
        assert encryptor.master_password == TEST_PASSWORD.encode('utf-8')

    def test_initialization_from_env_var(self, monkeypatch):
        """Test initialization from environment variable"""
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', TEST_PASSWORD)
        encryptor = DataEncryptor()
        assert encryptor.master_password == TEST_PASSWORD.encode('utf-8')

    def test_initialization_no_password_raises_error(self, monkeypatch):
        """Test that missing password raises error"""
        monkeypatch.delenv('TRADING_SECURITY_PASSWORD', raising=False)
        
        with pytest.raises(ValueError) as exc_info:
            DataEncryptor()
        
        assert "Master password required" in str(exc_info.value)

    def test_initialization_weak_password_raises_error(self):
        """Test that weak password raises error"""
        with pytest.raises(ValueError) as exc_info:
            DataEncryptor(master_password="short")
        
        assert "too weak" in str(exc_info.value)

    def test_initialization_minimum_password_length(self):
        """Test password at minimum length (16 chars)"""
        min_password = "A" * 16
        encryptor = DataEncryptor(master_password=min_password)
        assert encryptor.master_password == min_password.encode('utf-8')


# ============================================================================
# Key Derivation Tests
# ============================================================================

class TestKeyDerivation:
    """Test _derive_key method"""

    def test_derive_key_returns_32_bytes(self, encryptor):
        """Test that derived key is 32 bytes (256 bits)"""
        salt = b'0' * 16
        key = encryptor._derive_key(salt)
        
        assert len(key) == 32

    def test_derive_key_same_salt_same_key(self, encryptor):
        """Test that same salt produces same key"""
        salt = b'test_salt_123456'
        
        key1 = encryptor._derive_key(salt)
        key2 = encryptor._derive_key(salt)
        
        assert key1 == key2

    def test_derive_key_different_salt_different_key(self, encryptor):
        """Test that different salts produce different keys"""
        salt1 = b'salt1_123456789a'
        salt2 = b'salt2_123456789a'
        
        key1 = encryptor._derive_key(salt1)
        key2 = encryptor._derive_key(salt2)
        
        assert key1 != key2

    def test_derive_key_custom_iterations(self, encryptor):
        """Test key derivation with custom iterations"""
        salt = b'test_salt_123456'
        
        # Different iterations should produce different keys
        key1 = encryptor._derive_key(salt, iterations=10_000)
        key2 = encryptor._derive_key(salt, iterations=20_000)
        
        assert key1 != key2


# ============================================================================
# Data Encryption/Decryption Tests
# ============================================================================

class TestDataEncryption:
    """Test encrypt_data and decrypt_data methods"""

    def test_encrypt_decrypt_string(self, encryptor):
        """Test encryption/decryption of string"""
        original = "Sensitive trading data"
        
        encrypted = encryptor.encrypt_data(original, compress=False)
        decrypted = encryptor.decrypt_data(encrypted)
        
        assert decrypted == original

    def test_encrypt_decrypt_bytes(self, encryptor):
        """Test encryption/decryption of bytes"""
        original = b"Binary data: \x00\x01\x02"
        
        encrypted = encryptor.encrypt_data(original, compress=False)
        decrypted = encryptor.decrypt_data(encrypted, return_type='bytes')
        
        assert decrypted == original

    def test_encrypt_decrypt_dict(self, encryptor):
        """Test encryption/decryption of dictionary"""
        original = {
            'symbol': 'RELIANCE',
            'price': 2500.00,
            'quantity': 100
        }
        
        encrypted = encryptor.encrypt_data(original)
        decrypted = encryptor.decrypt_data(encrypted)
        
        assert decrypted == original

    def test_encrypt_decrypt_list(self, encryptor):
        """Test encryption/decryption of list"""
        original = [1, 2, 3, "test", {"key": "value"}]
        
        encrypted = encryptor.encrypt_data(original)
        decrypted = encryptor.decrypt_data(encrypted)
        
        assert decrypted == original

    def test_encryption_produces_different_ciphertext(self, encryptor):
        """Test that encrypting same data produces different ciphertext (due to random nonce)"""
        data = "Same data"
        
        encrypted1 = encryptor.encrypt_data(data)
        encrypted2 = encryptor.encrypt_data(data)
        
        # Ciphertext should be different due to random nonce
        assert encrypted1 != encrypted2
        
        # But both should decrypt to same data
        assert encryptor.decrypt_data(encrypted1) == data
        assert encryptor.decrypt_data(encrypted2) == data

    def test_encryption_with_compression(self, encryptor):
        """Test encryption with compression"""
        # Large repetitive data compresses well
        original = "A" * 10000
        
        encrypted_compressed = encryptor.encrypt_data(original, compress=True)
        encrypted_uncompressed = encryptor.encrypt_data(original, compress=False)
        
        # Compressed version should be smaller
        assert len(encrypted_compressed) < len(encrypted_uncompressed)
        
        # Both should decrypt correctly
        assert encryptor.decrypt_data(encrypted_compressed) == original
        assert encryptor.decrypt_data(encrypted_uncompressed) == original

    def test_decryption_wrong_password(self):
        """Test that decryption fails with wrong password"""
        encryptor1 = DataEncryptor(master_password="Password123456789")
        encryptor2 = DataEncryptor(master_password="DifferentPassword123")
        
        encrypted = encryptor1.encrypt_data("secret data")
        
        with pytest.raises(ValueError) as exc_info:
            encryptor2.decrypt_data(encrypted)
        
        assert "Decryption failed" in str(exc_info.value)

    def test_decryption_corrupted_data(self, encryptor):
        """Test that decryption fails with corrupted data"""
        original = "test data"
        encrypted = encryptor.encrypt_data(original)
        
        # Corrupt the encrypted data
        corrupted = encrypted[:-10] + b'\x00' * 10
        
        with pytest.raises(ValueError) as exc_info:
            encryptor.decrypt_data(corrupted)
        
        assert "Decryption failed" in str(exc_info.value)

    def test_decrypt_with_specific_return_type(self, encryptor):
        """Test decryption with specific return type"""
        original = {"key": "value"}
        encrypted = encryptor.encrypt_data(original)
        
        # Decrypt as string
        decrypted_str = encryptor.decrypt_data(encrypted, return_type='str')
        assert isinstance(decrypted_str, str)
        assert json.loads(decrypted_str) == original
        
        # Decrypt as dict
        decrypted_dict = encryptor.decrypt_data(encrypted, return_type='dict')
        assert isinstance(decrypted_dict, dict)
        assert decrypted_dict == original


# ============================================================================
# File Encryption Tests
# ============================================================================

class TestFileEncryption:
    """Test encrypt_file and decrypt_file methods"""

    def test_encrypt_file_basic(self, encryptor, temp_dir):
        """Test basic file encryption"""
        # Create test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("Sensitive data")
        
        # Encrypt
        encrypted_file = encryptor.encrypt_file(test_file)
        
        # Verify encrypted file exists
        assert encrypted_file.exists()
        assert encrypted_file.suffix == ".enc"

    def test_encrypt_file_not_found(self, encryptor, temp_dir):
        """Test encryption of non-existent file"""
        with pytest.raises(FileNotFoundError):
            encryptor.encrypt_file(temp_dir / "nonexistent.txt")

    def test_encrypt_decrypt_file_roundtrip(self, encryptor, temp_dir):
        """Test file encryption and decryption roundtrip"""
        # Create test file
        test_file = temp_dir / "data.json"
        test_data = {"key": "value", "number": 12345}
        test_file.write_text(json.dumps(test_data))
        
        # Encrypt
        encrypted_file = encryptor.encrypt_file(test_file)
        
        # Decrypt
        decrypted_file = encryptor.decrypt_file(encrypted_file)
        
        # Verify content
        decrypted_data = json.loads(decrypted_file.read_text())
        assert decrypted_data == test_data

    def test_encrypt_file_custom_output_path(self, encryptor, temp_dir):
        """Test file encryption with custom output path"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("data")
        
        custom_output = temp_dir / "encrypted.bin"
        encrypted_file = encryptor.encrypt_file(test_file, output_path=custom_output)
        
        assert encrypted_file == custom_output
        assert encrypted_file.exists()

    def test_encrypt_file_remove_original(self, encryptor, temp_dir):
        """Test file encryption with removal of original"""
        test_file = temp_dir / "test.txt"
        test_file.write_text("data")
        
        encrypted_file = encryptor.encrypt_file(test_file, remove_original=True)
        
        # Original should be removed
        assert not test_file.exists()
        assert encrypted_file.exists()

    def test_decrypt_file_custom_output(self, encryptor, temp_dir):
        """Test file decryption with custom output path"""
        # Create and encrypt file
        test_file = temp_dir / "test.txt"
        test_file.write_text("data")
        encrypted_file = encryptor.encrypt_file(test_file)
        
        # Decrypt to custom path
        custom_output = temp_dir / "decrypted.txt"
        decrypted_file = encryptor.decrypt_file(encrypted_file, output_path=custom_output)
        
        assert decrypted_file == custom_output
        assert decrypted_file.read_text() == "data"

    def test_decrypt_file_without_enc_extension(self, encryptor, temp_dir):
        """Test decryption of file without .enc extension"""
        # Create and encrypt file with custom extension
        test_file = temp_dir / "test.txt"
        test_file.write_text("data")
        encrypted_file = temp_dir / "encrypted.bin"
        encryptor.encrypt_file(test_file, output_path=encrypted_file)
        
        # Decrypt (should add .decrypted suffix)
        decrypted_file = encryptor.decrypt_file(encrypted_file)
        
        assert decrypted_file.suffix == ".decrypted"
        assert decrypted_file.read_text() == "data"


# ============================================================================
# Trade History Encryption Tests
# ============================================================================

class TestTradeHistoryEncryption:
    """Test encrypt_trade_history and decrypt_trade_history"""

    def test_encrypt_decrypt_trade_history(self, encryptor, temp_dir):
        """Test trade history encryption/decryption"""
        trades = [
            {'symbol': 'RELIANCE', 'pnl': 5000.00},
            {'symbol': 'TCS', 'pnl': 3000.00}
        ]
        
        output_file = temp_dir / "trades.enc"
        
        # Encrypt
        encryptor.encrypt_trade_history(trades, output_file)
        
        # Decrypt
        decrypted_trades = encryptor.decrypt_trade_history(output_file)
        
        assert decrypted_trades == trades

    def test_encrypt_empty_trade_history(self, encryptor, temp_dir):
        """Test encryption of empty trade list"""
        trades = []
        output_file = temp_dir / "empty_trades.enc"
        
        encryptor.encrypt_trade_history(trades, output_file)
        decrypted_trades = encryptor.decrypt_trade_history(output_file)
        
        assert decrypted_trades == []


# ============================================================================
# SecureArchiveManager Tests
# ============================================================================

class TestSecureArchiveManager:
    """Test SecureArchiveManager class"""

    def test_initialization_creates_directory(self, temp_dir):
        """Test that initialization creates archive directory"""
        archive_dir = temp_dir / "new_archives"
        
        manager = SecureArchiveManager(
            archive_dir=archive_dir,
            master_password=TEST_PASSWORD
        )
        
        assert archive_dir.exists()

    def test_create_archive(self, archive_manager):
        """Test creating an archive"""
        data = {"key": "value"}
        
        archive_path = archive_manager.create_archive(
            data=data,
            name="test_archive"
        )
        
        assert archive_path.exists()
        assert archive_path.suffix == ".enc"
        assert "test_archive" in archive_path.name

    def test_create_archive_with_metadata(self, archive_manager):
        """Test creating archive with metadata"""
        data = [1, 2, 3]
        metadata = {"count": 3, "type": "numbers"}
        
        archive_path = archive_manager.create_archive(
            data=data,
            name="numbers",
            metadata=metadata
        )
        
        # Load and verify
        loaded = archive_manager.load_archive(archive_path)
        
        assert loaded['data'] == data
        assert loaded['metadata'] == metadata
        assert 'created_at' in loaded
        assert loaded['name'] == "numbers"

    def test_list_archives_no_filter(self, archive_manager):
        """Test listing all archives"""
        # Create multiple archives
        archive_manager.create_archive(data=[1], name="archive1")
        archive_manager.create_archive(data=[2], name="archive2")
        
        archives = archive_manager.list_archives()
        
        assert len(archives) >= 2

    def test_list_archives_with_pattern(self, archive_manager):
        """Test listing archives with pattern filter"""
        # Create archives with different names
        archive_manager.create_archive(data=[1], name="trades")
        archive_manager.create_archive(data=[2], name="orders")
        
        # List only trades archives
        trades_archives = archive_manager.list_archives("trades_*")
        
        assert len(trades_archives) >= 1
        assert all("trades" in str(a) for a in trades_archives)

    def test_list_archives_sorted_newest_first(self, archive_manager):
        """Test that archives are sorted newest first"""
        import time

        # Create archives with time gap (1+ second to ensure different timestamp)
        archive1 = archive_manager.create_archive(data=[1], name="test")
        time.sleep(1.1)  # Wait for next second
        archive2 = archive_manager.create_archive(data=[2], name="test")

        archives = archive_manager.list_archives("test_*")

        # Should have 2 archives with different timestamps
        assert len(archives) == 2
        # Newest should be first
        assert archives[0] == archive2
        assert archives[1] == archive1

    def test_load_archive(self, archive_manager):
        """Test loading an archive"""
        data = {"symbol": "RELIANCE", "price": 2500}
        
        archive_path = archive_manager.create_archive(
            data=data,
            name="stock_data"
        )
        
        loaded = archive_manager.load_archive(archive_path)
        
        assert loaded['data'] == data
        assert 'created_at' in loaded
        assert 'metadata' in loaded


# ============================================================================
# Global Encryptor Tests
# ============================================================================

class TestGlobalEncryptor:
    """Test get_global_encryptor function"""

    def test_get_global_encryptor_creates_instance(self, monkeypatch):
        """Test that get_global_encryptor creates instance"""
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', TEST_PASSWORD)
        
        # Reset global instance
        import core.data_encryption as module
        module._global_encryptor = None
        
        encryptor = get_global_encryptor()
        
        assert encryptor is not None
        assert isinstance(encryptor, DataEncryptor)

    def test_get_global_encryptor_returns_same_instance(self, monkeypatch):
        """Test that subsequent calls return same instance"""
        monkeypatch.setenv('TRADING_SECURITY_PASSWORD', TEST_PASSWORD)
        
        # Reset global instance
        import core.data_encryption as module
        module._global_encryptor = None
        
        encryptor1 = get_global_encryptor()
        encryptor2 = get_global_encryptor()
        
        assert encryptor1 is encryptor2


# ============================================================================
# Edge Cases and Security Tests
# ============================================================================

class TestEdgeCasesAndSecurity:
    """Test edge cases and security properties"""

    def test_encrypt_empty_string(self, encryptor):
        """Test encryption of empty string"""
        encrypted = encryptor.encrypt_data("")
        decrypted = encryptor.decrypt_data(encrypted)
        
        assert decrypted == ""

    def test_encrypt_large_data(self, encryptor):
        """Test encryption of large data"""
        # 1 MB of data
        large_data = "A" * (1024 * 1024)
        
        encrypted = encryptor.encrypt_data(large_data, compress=True)
        decrypted = encryptor.decrypt_data(encrypted)
        
        assert decrypted == large_data

    def test_encryption_metadata_embedded(self, encryptor):
        """Test that encryption metadata is embedded in ciphertext"""
        data = "test"
        encrypted = encryptor.encrypt_data(data)
        
        # Encrypted data should contain metadata
        # Format: salt(16) + nonce(12) + metadata_len(2) + metadata + ciphertext
        assert len(encrypted) > 30  # At least salt + nonce + metadata_len

    def test_unicode_data_encryption(self, encryptor):
        """Test encryption of unicode data"""
        unicode_data = "文字列 émoji 🚀"
        
        encrypted = encryptor.encrypt_data(unicode_data)
        decrypted = encryptor.decrypt_data(encrypted)
        
        assert decrypted == unicode_data

    def test_nested_dict_encryption(self, encryptor):
        """Test encryption of nested dictionary"""
        nested = {
            'level1': {
                'level2': {
                    'level3': ['a', 'b', 'c']
                }
            }
        }
        
        encrypted = encryptor.encrypt_data(nested)
        decrypted = encryptor.decrypt_data(encrypted)
        
        assert decrypted == nested


if __name__ == "__main__":
    # Run tests with: pytest test_data_encryption.py -v
    pytest.main([__file__, "-v", "--tb=short"])
