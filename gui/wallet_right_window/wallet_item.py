from typing import Union
from src import enums

import customtkinter

from src import enums
from src.schemas.proxy_data import ProxyData
from src.schemas.wallet_data import WalletData
from gui.wallet_right_window.wallet_window import WalletWindow
from gui import constants


class WalletItem(customtkinter.CTkFrame):
    def __init__(
            self,
            master,
            grid: dict,
            wallet_data: WalletData,
            # on_wallet_save: Callable[[WalletData], None],
            index: int,
    ):

        super().__init__(master)

        self.wallet_data = wallet_data
        # self.on_wallet_save = on_wallet_save
        self.index = index

        self.frame = customtkinter.CTkFrame(master)
        self.frame.grid(**grid)

        self.frame.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=1, uniform="uniform")

        self.frame.grid_rowconfigure(0, weight=1)

        pad_y = 5

        self.chose_checkbox = customtkinter.CTkCheckBox(
            self.frame,
            text="",
            checkbox_width=20,
            checkbox_height=20,
            onvalue=True,
            offvalue=False,
            command=self.select_checkbox_event
        )
        self.chose_checkbox.grid(
            row=0,
            column=0,
            padx=(10, 0),
            pady=pad_y,
            sticky="w",
        )

        self.wallet_name_label = customtkinter.CTkLabel(
            self.frame,
            text=wallet_data.name if wallet_data.name is not None else f"Wallet {index + 1}",
            font=customtkinter.CTkFont(size=12, weight="bold")
        )
        self.wallet_name_label.grid(
            row=0,
            column=0,
            padx=(50, 0),
            pady=pad_y,
            sticky="w"
        )

        self.wallet_address_label = customtkinter.CTkLabel(
            self.frame,
            text=self.get_short_address(wallet_data.address),
            font=customtkinter.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.wallet_address_label.grid(
            row=0,
            column=1,
            padx=(0, 0),
            pady=pad_y,
        )

        pair_address = self.get_short_address(wallet_data.pair_address) if wallet_data.pair_address else "-"
        self.pair_address_label = customtkinter.CTkLabel(
            self.frame,
            text=pair_address,
            font=customtkinter.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.pair_address_label.grid(
            row=0,
            column=2,
            padx=(20, 0),
            pady=pad_y,
        )

        proxy = self.get_short_proxy(wallet_data.proxy)
        padx = self.get_proxy_field_coords(proxy)
        self.proxy_address_label = customtkinter.CTkLabel(
            self.frame,
            text=proxy,
            font=customtkinter.CTkFont(size=12, weight="bold")
        )
        self.proxy_address_label.grid(
            row=0,
            column=3,
            padx=(padx, 0),
            pady=pad_y,
            sticky="w"
        )

        self.wallet_status_label = customtkinter.CTkLabel(
            self.frame,
            text=wallet_data.wallet_status.title(),
            font=customtkinter.CTkFont(size=12, weight="bold")
        )
        self.wallet_status_label.grid(
            row=0,
            column=4,
            padx=(0, 28),
            pady=pad_y,
            sticky="e"
        )

        self.edit_button = customtkinter.CTkButton(
            self.frame,
            text="Edit",
            font=customtkinter.CTkFont(size=12, weight="bold"),
            width=45,
            height=25,
            command=self.edit_wallet_button_clicked
        )
        self.edit_button.grid(
            row=0,
            column=5,
            padx=(60, 0),
            pady=pad_y,
            sticky="w"
        )

        # EDIT WALLET
        self.edit_window = None

    def select_checkbox_event(self):
        self.master.update_selected_wallets_labels()

    @property
    def is_chosen(self):
        return self.chose_checkbox.get()

    @staticmethod
    def get_short_address(
            address: str
    ):
        return address[:6] + "..." + address[-4:]

    @staticmethod
    def get_short_proxy(
            proxy: Union[ProxyData, None] = None,
    ):
        if isinstance(proxy, ProxyData) and proxy.host is not None:
            return f"{proxy.host}" + (f":{proxy.port}" if proxy.port is not None else "")
        else:
            return ""

    @staticmethod
    def get_proxy_field_coords(proxy_item: str) -> int:
        if not proxy_item:
            return 0

        max_len = 20
        padx_for_max_len = 35

        proxy_len = len(proxy_item)
        if proxy_len > max_len:
            padx = (proxy_len - max_len + padx_for_max_len)

        elif proxy_len < max_len * 0.6:
            padx = (max_len - proxy_len + padx_for_max_len) // 0.6

        elif proxy_len <= max_len * 0.8:
            padx = (max_len - proxy_len + padx_for_max_len) // 0.85

        elif proxy_len <= max_len * 0.9:
            padx = (max_len - proxy_len + padx_for_max_len) // 0.9

        else:
            padx = padx_for_max_len

        return padx

    def update_wallet_data(self, wallet_data: WalletData):
        self.wallet_data = wallet_data

        self.wallet_name_label.configure(text=wallet_data.name if wallet_data.name is not None else f"Wallet {self.index + 1}")
        self.wallet_address_label.configure(text=self.get_short_address(wallet_data.address))
        self.pair_address_label.configure(text=self.get_short_address(wallet_data.pair_address))

        padx_proxy = self.get_proxy_field_coords(self.get_short_proxy(wallet_data.proxy))
        self.proxy_address_label.configure(text=self.get_short_proxy(wallet_data.proxy))
        self.proxy_address_label.grid(padx=(padx_proxy, 0))

    def edit_wallet_button_clicked(self):
        if self.edit_window is not None:
            return

        self.edit_window = WalletWindow(
            master=self.master,
            wallet_data=self.wallet_data,
            on_wallet_save=self.edit_wallet_callback,
        )

        self.edit_window.protocol(
            "WM_DELETE_WINDOW", self.close_edit_wallet_window
        )

    def edit_wallet_callback(self, wallet_data: WalletData):
        if wallet_data is None:
            return

        self.update_wallet_data(wallet_data)
        self.close_edit_wallet_window()

    def close_edit_wallet_window(self):
        self.edit_window.close()
        self.edit_window = None

    def set_wallet_active(self):
        self.wallet_status_label.configure(text=enums.WalletStatus.active.title())
        self.frame.configure(border_width=1, border_color=constants.ACTIVE_ACTION_HEX)

    def set_wallet_completed(self):
        self.wallet_status_label.configure(text=enums.WalletStatus.completed.title())
        self.frame.configure(border_width=1, border_color=constants.SUCCESS_HEX)

    def set_wallet_inactive(self):
        self.wallet_status_label.configure(text=enums.WalletStatus.inactive.title())
        self.frame.configure(border_width=0)


