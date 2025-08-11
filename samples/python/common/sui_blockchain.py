"""SUI区块链交互模块

封装与SUI Move task_manager合约的所有交互逻辑。
"""

import logging
import subprocess
import tempfile
import os
from typing import Optional, Dict, Any
import time

from .sui_config import SUIConfig


logger = logging.getLogger(__name__)


class SUITaskManager:
    """SUI任务管理器区块链交互类"""
    
    def __init__(self, config: SUIConfig):
        self.config = config
        
    async def create_task(self, task_id: str, service_agent: str, amount_sui: int, 
                   deadline_seconds: int, description: str) -> Dict[str, Any]:
        """创建任务并托管SUI
        
        Args:
            task_id: 任务ID字符串
            service_agent: 服务提供者地址
            amount_sui: 支付金额（MIST为单位，1 SUI = 10^9 MIST）
            deadline_seconds: 任务期限（秒）
            description: 任务描述
            
        Returns:
            包含交易结果的字典
        """
        try:
            # 创建JavaScript脚本来执行create_task交易（使用CommonJS格式）
            js_script = f'''
            const {{ Ed25519Keypair }} = require("@mysten/sui/keypairs/ed25519");
            const {{ Transaction }} = require("@mysten/sui/transactions");
            const {{ SuiClient, getFullnodeUrl }} = require("@mysten/sui/client");
            
            async function createTask() {{
                try {{
                    const taskAgentKeyPair = Ed25519Keypair.fromSecretKey("{self.config.private_key}");
                    const suiClient = new SuiClient({{ url: getFullnodeUrl("{self.config.network}") }});
                    
                    const tx = new Transaction();
                    
                    // 添加支付资金
                    const [coin] = tx.splitCoins(tx.gas, [tx.pure.u64({amount_sui})]);
                    
                    // 调用create_task方法
                    tx.moveCall({{
                        target: `{self.config.task_manager_package_id}::task_manager::create_task`,
                        arguments: [
                            tx.pure.string("{task_id}"),
                            tx.pure.address("{service_agent}"),
                            coin,
                            tx.pure.u64({deadline_seconds}),
                            tx.pure.string("{description}"),
                            tx.object("{self.config.task_manager_id}"),
                            tx.object("0x6")
                        ]
                    }});
                    
                    tx.setGasBudget(20000000);
                    
                    const txResult = await suiClient.signAndExecuteTransaction({{
                        transaction: tx,
                        signer: taskAgentKeyPair,
                        options: {{
                            showEffects: true,
                            showObjectChanges: true,
                            showEvents: true
                        }}
                    }});
                    
                    console.log("SUCCESS");
                    console.log(`TX_HASH:${{txResult.digest}}`);
                    
                    // 查找TaskCreatedEvent
                    const createdEvent = txResult.events?.find(event =>
                        event.type.includes("TaskCreatedEvent")
                    );
                    
                    if (createdEvent && createdEvent.parsedJson) {{
                        console.log(`TASK_OBJECT_ID:${{createdEvent.parsedJson.task_object_id}}`);
                    }}
                    
                    // 查找创建的Task对象
                    const taskObject = txResult.objectChanges?.find(change =>
                        change.type === 'created' && 
                        change.objectType && 
                        change.objectType.includes('Task')
                    );
                    
                    if (taskObject) {{
                        console.log(`TASK_OBJECT_ID:${{taskObject.objectId}}`);
                    }}
                    
                    process.exit(0);
                }} catch (error) {{
                    console.error("ERROR:", error.message);
                    process.exit(1);
                }}
            }}
            
            createTask();
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
                                      capture_output=True, text=True, timeout=120,
                                      env=env)
                os.unlink(temp_file_path)
                
                if result.returncode == 0:
                    # 解析输出
                    lines = result.stdout.strip().split('\n')
                    tx_hash = None
                    task_object_id = None
                    
                    for line in lines:
                        if line.startswith('TX_HASH:'):
                            tx_hash = line.split('TX_HASH:')[1]
                        elif line.startswith('TASK_OBJECT_ID:'):
                            task_object_id = line.split('TASK_OBJECT_ID:')[1]
                    
                    print(f"[SUI] Task created successfully: {task_id}, you can check the task on https://suiscan.xyz/{self.config.network}/tx/{tx_hash}")
                    
                    return {
                        'success': True,
                        'tx_hash': tx_hash,
                        'task_object_id': task_object_id,
                        'gas_used': 0,  # SUI计算gas的方式不同，这里简化
                        'vm_status': 'Success'
                    }
                else:
                    error_msg = result.stderr or result.stdout
                    logger.error(f"Error creating task on SUI: {error_msg}")
                    return {'success': False, 'error': error_msg}
                    
            except subprocess.TimeoutExpired:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                return {'success': False, 'error': 'Transaction timeout (120 seconds)'}
            except Exception as e:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                logger.error(f"Error executing create_task: {e}")
                return {'success': False, 'error': str(e)}
                
        except Exception as e:
            logger.error(f"Error creating task on SUI: {e}")
            return {'success': False, 'error': str(e)}
    
    async def complete_task(self, task_object_id: str) -> Dict[str, Any]:
        """完成任务
        
        Args:
            task_object_id: 任务对象ID（SUI特有）
            
        Returns:
            包含交易结果的字典
        """
        try:
            # 获取服务代理私钥
            service_agent_key = os.getenv('SERVICE_AGENT_PRIVATE_KEY')
            if not service_agent_key:
                return {'success': False, 'error': 'SERVICE_AGENT_PRIVATE_KEY not found'}
            
            # 创建JavaScript脚本来执行complete_task交易（使用CommonJS格式）
            js_script = f'''
            const {{ Ed25519Keypair }} = require("@mysten/sui/keypairs/ed25519");
            const {{ Transaction }} = require("@mysten/sui/transactions");
            const {{ SuiClient, getFullnodeUrl }} = require("@mysten/sui/client");
            
            async function completeTask() {{
                try {{
                    const serviceAgentKeyPair = Ed25519Keypair.fromSecretKey("{service_agent_key}");
                    const suiClient = new SuiClient({{ url: getFullnodeUrl("{self.config.network}") }});
                    
                    const tx = new Transaction();
                    tx.moveCall({{
                        target: `{self.config.task_manager_package_id}::task_manager::complete_task`,
                        arguments: [
                            tx.object("{task_object_id}"),
                            tx.object("{self.config.task_manager_id}"),
                            tx.object("0x6")
                        ]
                    }});
                    
                    tx.setGasBudget(20000000);
                    
                    const txResult = await suiClient.signAndExecuteTransaction({{
                        transaction: tx,
                        signer: serviceAgentKeyPair,
                        options: {{
                            showEffects: true,
                            showObjectChanges: true,
                            showEvents: true
                        }}
                    }});
                    
                    console.log("SUCCESS");
                    console.log(`TX_HASH:${{txResult.digest}}`);
                    
                    // 检查完成事件
                    const completedEvent = txResult.events?.find(event =>
                        event.type.includes("TaskCompletedEvent")
                    );
                    
                    if (completedEvent) {{
                        console.log("TASK_COMPLETED");
                    }}
                    
                    process.exit(0);
                }} catch (error) {{
                    console.error("ERROR:", error.message);
                    process.exit(1);
                }}
            }}
            
            completeTask();
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
                                      capture_output=True, text=True, timeout=60,
                                      env=env)
                os.unlink(temp_file_path)
                
                if result.returncode == 0:
                    # 解析输出
                    lines = result.stdout.strip().split('\n')
                    tx_hash = None
                    
                    for line in lines:
                        if line.startswith('TX_HASH:'):
                            tx_hash = line.split('TX_HASH:')[1]
                    
                    logger.info(f"[SUI] Task completed ! check transaction on https://suiscan.xyz/{self.config.network}/tx/{tx_hash}")
                    
                    return {'success': True, 'tx_hash': tx_hash}
                else:
                    error_msg = result.stderr or result.stdout
                    logger.error(f"Error completing task on SUI: {error_msg}")
                    return {'success': False, 'error': error_msg}
                    
            except subprocess.TimeoutExpired:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                return {'success': False, 'error': 'Transaction timeout (60 seconds)'}
            except Exception as e:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                logger.error(f"Error executing complete_task: {e}")
                return {'success': False, 'error': str(e)}
                
        except Exception as e:
            logger.error(f"Error completing task on SUI: {e}")
            return {'success': False, 'error': str(e)}
    
    # Mock 方法实现
    async def cancel_task(self, task_id: str) -> Dict[str, Any]:
        """取消任务 - Mock实现
        
        Args:
            task_id: 任务ID字符串
            
        Returns:
            包含Mock结果的字典
        """
        logger.info(f"[SUI] Mock: cancel_task called for task_id: {task_id}")
        return {
            'success': True,
            'mock': True,
            'message': 'Cancel task functionality not implemented in POC',
            'task_id': task_id,
            'tx_hash': f'mock_cancel_tx_{int(time.time())}'
        }
    
    async def get_task_info(self, task_agent_address: str, task_id: str) -> Dict[str, Any]:
        """查询任务信息 - Mock实现
        
        Args:
            task_agent_address: 任务创建者地址
            task_id: 任务ID字符串
            
        Returns:
            包含Mock任务信息的字典
        """
        logger.info(f"[SUI] Mock: get_task_info called for task_agent: {task_agent_address}, task_id: {task_id}")
        return {
            'mock': True,
            'message': 'Get task info functionality not implemented in POC',
            'task_agent': task_agent_address,
            'service_agent': '0x0000000000000000000000000000000000000000000000000000000000000000',
            'pay_amount': 1000000000,  # 1 SUI in MIST
            'created_at': int(time.time()),
            'deadline': int(time.time()) + 86400,  # 24小时后
            'is_completed': False,
            'is_cancelled': False,
            'description': f'Mock task info for {task_id}'
        }
    
    async def get_task_stats(self, task_agent_address: str) -> Dict[str, Any]:
        """获取任务统计信息 - Mock实现
        
        Args:
            task_agent_address: 任务创建者地址
            
        Returns:
            包含Mock统计信息的字典
        """
        logger.info(f"[SUI] Mock: get_task_stats called for task_agent: {task_agent_address}")
        return {
            'mock': True,
            'message': 'Get task stats functionality not implemented in POC',
            'total_tasks': 5,
            'completed_tasks': 3,
            'cancelled_tasks': 1
        }
    
    async def is_task_expired(self, task_agent_address: str, task_id: str) -> bool:
        """检查任务是否已过期 - Mock实现
        
        Args:
            task_agent_address: 任务创建者地址
            task_id: 任务ID字符串
            
        Returns:
            Mock结果，总是返回False
        """
        logger.info(f"[SUI] Mock: is_task_expired called for task_agent: {task_agent_address}, task_id: {task_id}")
        return False  # Mock实现总是返回未过期


class SUISignatureManager:
    """SUI签名管理器"""
    
    def __init__(self, config: SUIConfig):
        self.config = config
    
    def sign_message(self, message: str) -> Optional[str]:
        """使用Ed25519签名消息
        
        Args:
            message: 要签名的消息
            
        Returns:
            签名的十六进制字符串
        """
        try:
            # 创建临时JavaScript脚本来签名（使用CommonJS格式）
            js_script = f'''
            const {{ Ed25519Keypair }} = require("@mysten/sui/keypairs/ed25519");
            
            try {{
                const keypair = Ed25519Keypair.fromSecretKey("{self.config.private_key}");
                const messageBytes = new TextEncoder().encode("{message}");
                keypair.sign(messageBytes).then(signature => {{
                    console.log(signature.signature);
                    process.exit(0);
                }}).catch(error => {{
                    console.error("Error:", error.message);
                    process.exit(1);
                }});
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
                    return result.stdout.strip()
                else:
                    logger.error(f"Failed to sign message: {result.stderr}")
                    return None
            except Exception as e:
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                logger.error(f"Error signing message: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error in sign_message: {e}")
            return None
    
    def verify_signature(self, message: str, signature: str, public_key: str) -> bool:
        """验证Ed25519签名
        
        Args:
            message: 原始消息
            signature: 签名
            public_key: 公钥
            
        Returns:
            签名是否有效
        """
        try:
            # SUI签名验证的简化实现
            # 在生产环境中，这里需要实现真正的签名验证逻辑
            logger.info(f"[SUI] Mock signature verification for message: {message}")
            return True  # 简化实现
        except Exception as e:
            logger.error(f"Error verifying signature: {e}")
            return False