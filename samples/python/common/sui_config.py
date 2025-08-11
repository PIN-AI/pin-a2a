"""SUI区块链配置模块

提供SUI网络连接、账户管理和合约配置功能。
"""
import logging
import os
import subprocess
import tempfile
from typing import Optional

# Configure logging to reduce verbosity
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


class SUIConfig:
    """SUI区块链配置类"""
    
    def __init__(self, private_key: Optional[str] = None, network: Optional[str] = None):
        # 网络配置
        self.network = network or os.getenv('SUI_NETWORK', 'testnet')
        self.node_url = os.getenv('SUI_NODE_URL', 'https://fullnode.testnet.sui.io:443')
        
        # 账户配置
        self.private_key = private_key or os.getenv('TASK_AGENT_PRIVATE_KEY')
        if not self.private_key:
            raise ValueError("No SUI private key provided")
            
        # 移除前缀（如果存在）
        if self.private_key.startswith('suiprivkey'):
            # SUI私钥格式: suiprivkey1...
            pass  # 保持原格式
        elif self.private_key.startswith('0x'):
            self.private_key = self.private_key[2:]
        
        # 获取地址
        self.address = self._get_address_from_private_key()
        
        # 打印账户地址
        logger.info(f"SUI Config account address: {self.address}")
        
        # 合约配置
        self.task_manager_package_id = os.getenv('TASK_MANAGER_PACKAGE_ID', '0x73d3dd28f146f77c625eb7c631da0855acc95b1a9d922eafbd46d7d3ad9e4d22')
        self.task_manager_id = os.getenv('TASK_MANAGER_ID', '0x8daf22f074cee2b8f4a06ba3dce996a0100ac5c4d6f211664f34f4f0134a563f')
        self.module_name = 'task_manager'
        
        # 确保地址格式正确
        if not self.task_manager_package_id.startswith('0x'):
            self.task_manager_package_id = '0x' + self.task_manager_package_id
        if not self.task_manager_id.startswith('0x'):
            self.task_manager_id = '0x' + self.task_manager_id
    
    def _get_address_from_private_key(self) -> str:
        """从私钥获取SUI地址"""
        try:
            # 创建临时JavaScript脚本来获取地址（使用CommonJS格式）
            js_script = f'''
            const {{ Ed25519Keypair }} = require("@mysten/sui/keypairs/ed25519");
            
            try {{
                const keypair = Ed25519Keypair.fromSecretKey("{self.private_key}");
                const address = keypair.toSuiAddress();
                console.log(address);
                process.exit(0);
            }} catch (error) {{
                console.error("Error:", error.message);
                process.exit(1);
            }}
            '''
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as temp_file:
                temp_file.write(js_script)
                temp_file_path = temp_file.name
            
            try:
                # 设置NODE_PATH环境变量，确保能找到demo/ui/node_modules
                node_modules_path = "/Users/pis/workspace/PIN/pin-a2a/demo/ui/node_modules"
                env = os.environ.copy()
                env['NODE_PATH'] = node_modules_path
                
                result = subprocess.run(['node', temp_file_path], 
                                      capture_output=True, text=True, timeout=30,
                                      env=env)
                os.unlink(temp_file_path)
                
                if result.returncode == 0:
                    address = result.stdout.strip()
                    logger.info(f"Successfully got SUI address from private key: {address}")
                    return address
                else:
                    logger.error(f"Failed to get address: {result.stderr}")
                    # 如果JavaScript执行失败，返回一个基于私钥的确定性地址
                    return self._get_deterministic_address()
            except Exception as e:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                logger.error(f"Error getting address: {e}")
                return self._get_deterministic_address()
                
        except Exception as e:
            logger.error(f"Error in _get_address_from_private_key: {e}")
            return self._get_deterministic_address()
    
    def _get_deterministic_address(self) -> str:
        """基于私钥生成确定性地址（用于SUI SDK不可用时）"""
        import hashlib
        # 使用私钥的哈希来生成一个确定性的地址
        hash_obj = hashlib.sha256(self.private_key.encode())
        # 取前32字节作为地址（SUI地址长度）
        address_bytes = hash_obj.digest()[:32]
        address = "0x" + address_bytes.hex()
        logger.warning(f"Using deterministic address based on private key: {address}")
        return address
    
    async def get_account_balance(self, account_address=None) -> int:
        """获取账户SUI余额（以MIST为单位，1 SUI = 10^9 MIST）"""
        if account_address is None:
            account_address = self.address
        
        if account_address is None:
            raise ValueError("No account address available")
        
        try:
            # 创建临时JavaScript脚本来获取余额（使用CommonJS格式）
            js_script = f'''
            const {{ SuiClient, getFullnodeUrl }} = require("@mysten/sui/client");
            
            async function getBalance() {{
                try {{
                    const suiClient = new SuiClient({{ url: getFullnodeUrl("{self.network}") }});
                    const balance = await suiClient.getBalance({{
                        owner: "{account_address}"
                    }});
                    console.log(balance.totalBalance);
                    process.exit(0);
                }} catch (error) {{
                    console.error("Error:", error.message);
                    process.exit(1);
                }}
            }}
            
            getBalance();
            '''
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as temp_file:
                temp_file.write(js_script)
                temp_file_path = temp_file.name
            
            try:
                # 设置NODE_PATH环境变量，确保能找到demo/ui/node_modules
                node_modules_path = "/Users/pis/workspace/PIN/pin-a2a/demo/ui/node_modules"
                env = os.environ.copy()
                env['NODE_PATH'] = node_modules_path
                
                result = subprocess.run(['node', temp_file_path], 
                                      capture_output=True, text=True, timeout=30,
                                      env=env)
                os.unlink(temp_file_path)
                
                if result.returncode == 0:
                    return int(result.stdout.strip())
                else:
                    logger.error(f"Failed to get balance: {result.stderr}")
                    return 0
            except Exception as e:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                logger.error(f"Error getting balance: {e}")
                return 0
                
        except Exception as e:
            logger.error(f"Error in get_account_balance: {e}")
            return 0
    
    def get_module_function_name(self, function_name: str) -> str:
        """获取完整的模块函数名"""
        return f"{self.task_manager_package_id}::{self.module_name}::{function_name}"
    
    async def is_connected(self) -> bool:
        """检查是否连接到SUI网络"""
        try:
            # 创建临时JavaScript脚本来检查连接（使用CommonJS格式）
            js_script = f'''
            const {{ SuiClient, getFullnodeUrl }} = require("@mysten/sui/client");
            
            async function checkConnection() {{
                try {{
                    const suiClient = new SuiClient({{ url: getFullnodeUrl("{self.network}") }});
                    const chainId = await suiClient.getChainIdentifier();
                    console.log("connected");
                    process.exit(0);
                }} catch (error) {{
                    console.error("Error:", error.message);
                    process.exit(1);
                }}
            }}
            
            checkConnection();
            '''
            
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as temp_file:
                temp_file.write(js_script)
                temp_file_path = temp_file.name
            
            try:
                # 设置NODE_PATH环境变量，确保能找到demo/ui/node_modules
                node_modules_path = "/Users/pis/workspace/PIN/pin-a2a/demo/ui/node_modules"
                env = os.environ.copy()
                env['NODE_PATH'] = node_modules_path
                
                result = subprocess.run(['node', temp_file_path], 
                                      capture_output=True, text=True, timeout=30,
                                      env=env)
                os.unlink(temp_file_path)
                
                return result.returncode == 0
            except Exception as e:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                logger.error(f"Connection check failed: {e}")
                return False
                
        except Exception as e:
            logger.error(f"Error in is_connected: {e}")
            return False
    
    def __str__(self) -> str:
        return f"SUIConfig(network={self.network}, address={self.address}, package={self.task_manager_package_id}::{self.module_name})"