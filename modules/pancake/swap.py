import time
from typing import Union, TYPE_CHECKING

from aptos_sdk.account import Account
from aptos_sdk.transactions import EntryFunction
from aptos_sdk.transactions import Serializer
from aptos_sdk.transactions import TransactionArgument
from aptos_sdk.type_tag import TypeTag
from aptos_sdk.type_tag import StructTag
from loguru import logger

from modules.base import SwapModuleBase
from utils.delay import get_delay
from modules.pancake.math import get_amount_in
from src.schemas.action_models import TransactionPayloadData
from src.schemas.action_models import ModuleExecutionResult
from src import enums


if TYPE_CHECKING:
    from src.schemas.tasks import PancakeSwapTask
    from src.schemas.wallet_data import WalletData


class PancakeSwap(SwapModuleBase):
    def __init__(
            self,
            account: Account,
            task: 'PancakeSwapTask',
            base_url: str,
            wallet_data: 'WalletData',
            proxies: dict = None
    ):
        super().__init__(
            account=account,
            task=task,
            base_url=base_url,
            proxies=proxies,
            wallet_data=wallet_data
        )

        self.account = account
        self.task = task

        self.router_address = self.get_address_from_hex(
            "0xc7efb4076dbe143cbcd98cfaaa929ecfc8f299203dfff63b95ccb6bfe19850fa"
        )

    def get_token_pair_reserve(self) -> Union[dict, None]:
        coin_x = self.coin_x.contract_address
        coin_y = self.coin_y.contract_address

        data = self.get_token_reserve(
            resource_address=self.router_address,
            payload=f"{self.router_address}::swap::TokenPairReserve"
                    f"<{coin_x}, {coin_y}>"
        )

        if data is False:
            logger.error("Error getting token pair reserve")
            return None

        if data is not None:
            reserve_x = data["data"]["reserve_x"]
            reserve_y = data["data"]["reserve_y"]

            return {
                coin_x: reserve_x,
                coin_y: reserve_y
            }
        else:

            reversed_data = self.get_token_reserve(
                resource_address=self.router_address,
                payload=f"{self.router_address}::swap::TokenPairReserve"
                        f"<{coin_y}, {coin_x}>"
            )
            if not reversed_data:
                logger.error("Error getting token pair reserve")
                return None

            reserve_x = reversed_data["data"]["reserve_x"]
            reserve_y = reversed_data["data"]["reserve_y"]

            return {
                coin_x: reserve_y,
                coin_y: reserve_x
            }

    def get_amount_in(
            self,
            amount_out: int,
            coin_x_address: str,
            coin_y_address: str
    ) -> Union[int, None]:
        tokens_reserve: dict = self.get_token_pair_reserve()
        if tokens_reserve is None:
            return None

        reserve_x = int(tokens_reserve[coin_x_address])
        reserve_y = int(tokens_reserve[coin_y_address])

        if reserve_x is None or reserve_y is None:
            return None

        amount_in = get_amount_in(
            amount_out=amount_out,
            reserve_x=reserve_x,
            reserve_y=reserve_y
        )

        return amount_in

    def build_transaction_payload(self) -> Union[TransactionPayloadData, None]:
        amount_out_wei = self.calculate_amount_out_from_balance(coin_x=self.coin_x)
        if amount_out_wei is None:
            return None

        amount_in_wei = self.get_amount_in(
            amount_out=amount_out_wei,
            coin_x_address=self.coin_x.contract_address,
            coin_y_address=self.coin_y.contract_address
        )
        if amount_in_wei is None:
            return None

        amount_in_with_slippage = int(amount_in_wei * (1 - (self.task.slippage / 100)))

        amount_out_decimals = amount_out_wei / 10 ** self.token_x_decimals
        amount_in_decimals = amount_in_wei / 10 ** self.token_y_decimals
        transaction_args = [
            TransactionArgument(int(amount_out_wei), Serializer.u64),
            TransactionArgument(int(amount_in_with_slippage), Serializer.u64)
        ]

        payload = EntryFunction.natural(
            f"{self.router_address}::router",
            "swap_exact_input",
            [
                TypeTag(StructTag.from_str(self.coin_x.contract_address)),
                TypeTag(StructTag.from_str(self.coin_y.contract_address))
            ],
            transaction_args
        )

        return TransactionPayloadData(
            payload=payload,
            amount_x_decimals=amount_out_decimals,
            amount_y_decimals=amount_in_decimals
        )

    def build_reverse_transaction_payload(self) -> Union[TransactionPayloadData, None]:
        wallet_y_balance_wei = self.get_wallet_token_balance(
            wallet_address=self.account.address(),
            token_address=self.coin_y.contract_address
        )

        if wallet_y_balance_wei == 0:
            logger.error(f"Wallet {self.coin_y.symbol.upper()} balance = 0")
            return None

        if self.initial_balance_y_wei is None:
            logger.error(f"Error while getting initial balance of {self.coin_y.symbol.upper()}")
            return None

        amount_out_y_wei = wallet_y_balance_wei - self.initial_balance_y_wei
        if amount_out_y_wei <= 0:
            logger.error(f"Wallet {self.coin_y.symbol.upper()} balance less than initial balance")
            return None

        amount_in_x_wei = self.get_amount_in(
            amount_out=amount_out_y_wei,
            coin_x_address=self.coin_y.contract_address,
            coin_y_address=self.coin_x.contract_address
        )
        if amount_in_x_wei is None:
            return None

        amount_in_x_with_slippage_wei = int(amount_in_x_wei * (1 - (self.task.slippage / 100)))
        amount_out_y_decimals = amount_out_y_wei / 10 ** self.token_y_decimals
        amount_in_x_decimals = amount_in_x_wei / 10 ** self.token_x_decimals

        transaction_args = [
            TransactionArgument(int(amount_out_y_wei), Serializer.u64),
            TransactionArgument(int(amount_in_x_with_slippage_wei), Serializer.u64)
        ]

        payload = EntryFunction.natural(
            f"{self.router_address}::router",
            "swap_exact_input",
            [
                TypeTag(StructTag.from_str(self.coin_y.contract_address)),
                TypeTag(StructTag.from_str(self.coin_x.contract_address))
            ],
            transaction_args
        )

        return TransactionPayloadData(
            payload=payload,
            amount_x_decimals=amount_out_y_decimals,
            amount_y_decimals=amount_in_x_decimals
        )

    def send_txn(self) -> ModuleExecutionResult:
        if self.check_local_tokens_data() is False:
            self.module_execution_result.execution_status = enums.ModuleExecutionStatus.ERROR
            self.module_execution_result.execution_info = f"Failed to fetch local tokens data"
            return self.module_execution_result

        txn_payload_data = self.build_transaction_payload()
        if txn_payload_data is None:
            self.module_execution_result.execution_status = enums.ModuleExecutionStatus.ERROR
            self.module_execution_result.execution_info = "Error while building transaction payload"
            return self.module_execution_result

        txn_status = self.send_swap_type_txn(
            account=self.account,
            txn_payload_data=txn_payload_data
        )

        ex_status = txn_status.execution_status

        if ex_status != enums.ModuleExecutionStatus.SUCCESS and ex_status != enums.ModuleExecutionStatus.SENT:
            return txn_status

        if self.task.reverse_action is True:
            delay = get_delay(self.task.min_delay_sec, self.task.max_delay_sec)
            logger.info(f"Waiting {delay} seconds before reverse action")
            time.sleep(delay)

            reverse_txn_payload_data = self.build_reverse_transaction_payload()
            if reverse_txn_payload_data is None:
                self.module_execution_result.execution_status = enums.ModuleExecutionStatus.ERROR
                self.module_execution_result.execution_info = "Error while building reverse transaction payload"
                return self.module_execution_result

            reverse_txn_status = self.send_swap_type_txn(
                account=self.account,
                txn_payload_data=reverse_txn_payload_data,
                is_reverse=True
            )

            return reverse_txn_status

        return txn_status





