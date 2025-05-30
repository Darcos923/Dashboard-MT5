import streamlit as st
import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime, timedelta, date
import time
import altair as alt
import numpy as np

st.set_page_config(page_title="Dashboard MT5 Multi-Cuenta Pro", layout="wide")


def initialize_mt5(account_details):
    login = account_details["login"]
    password = account_details["password"]
    server = account_details["server"]
    mt5_path = account_details.get("path", None)
    init_params = {}
    if mt5_path and mt5_path.strip():
        init_params["path"] = mt5_path
    current_mt5_account_info = mt5.account_info()
    if current_mt5_account_info and current_mt5_account_info.login == login:
        st.session_state.connected_account_login = login
        st.session_state.current_account_currency = current_mt5_account_info.currency
        st.session_state.mt5_initialized_globally = True
        return True
    if (
        st.session_state.get("connected_account_login")
        and st.session_state.connected_account_login != login
    ):
        mt5.shutdown()
        st.session_state.connected_account_login = None
        st.session_state.current_account_currency = None
        st.session_state.mt5_initialized_globally = False
        time.sleep(0.5)
    if not st.session_state.get("mt5_initialized_globally", False):
        if not mt5.initialize(**init_params):
            st.error(
                f"initialize() falló para {login}, error code = {mt5.last_error()}"
            )
            st.session_state.mt5_initialized_globally = False
            return False
        st.session_state.mt5_initialized_globally = True
    authorized = mt5.login(login, password=password, server=server)
    if authorized:
        account_info = mt5.account_info()
        if account_info:
            st.success(
                f"Conectado a la cuenta #{account_info.login} ({account_info.name}) en {account_info.server}"
            )
            st.session_state.connected_account_login = account_info.login
            st.session_state.current_account_currency = account_info.currency
            return True
        else:
            st.error(
                f"Fallo al obtener información de la cuenta {login} después del login, error code = {mt5.last_error()}"
            )
            mt5.shutdown()
            st.session_state.connected_account_login = None
            st.session_state.current_account_currency = None
            st.session_state.mt5_initialized_globally = False
            return False
    else:
        st.error(
            f"Fallo al conectar a la cuenta #{login}, error code = {mt5.last_error()}"
        )
        mt5.shutdown()
        st.session_state.connected_account_login = None
        st.session_state.current_account_currency = None
        st.session_state.mt5_initialized_globally = False
        return False


def get_open_orders():
    if not st.session_state.get("connected_account_login"):
        return pd.DataFrame()
    account_info_current = mt5.account_info()
    if (
        not account_info_current
        or account_info_current.login != st.session_state.connected_account_login
    ):
        return pd.DataFrame()
    orders = mt5.orders_get()
    if orders is None or len(orders) == 0:
        return pd.DataFrame()
    df_orders = pd.DataFrame(list(orders), columns=orders[0]._asdict().keys())
    relevant_cols = {
        "ticket": "Ticket",
        "time_setup_msc": "Time Setup",
        "type": "Type",
        "magic": "Magic",
        "symbol": "Symbol",
        "volume_current": "Volume",
        "price_open": "Price Open",
        "sl": "SL",
        "tp": "TP",
    }
    df_orders = df_orders[list(relevant_cols.keys())].rename(columns=relevant_cols)
    order_type_map = {
        mt5.ORDER_TYPE_BUY: "BUY",
        mt5.ORDER_TYPE_SELL: "SELL",
        mt5.ORDER_TYPE_BUY_LIMIT: "BUY LIMIT",
        mt5.ORDER_TYPE_SELL_LIMIT: "SELL LIMIT",
        mt5.ORDER_TYPE_BUY_STOP: "BUY STOP",
        mt5.ORDER_TYPE_SELL_STOP: "SELL STOP",
        mt5.ORDER_TYPE_BUY_STOP_LIMIT: "BUY STOP LIMIT",
        mt5.ORDER_TYPE_SELL_STOP_LIMIT: "SELL STOP LIMIT",
    }
    df_orders["Type"] = df_orders["Type"].map(order_type_map)
    df_orders["Time Setup"] = pd.to_datetime(df_orders["Time Setup"], unit="ms")
    df_orders["SL"] = df_orders["SL"].apply(lambda x: np.nan if x == 0.0 else x)
    df_orders["TP"] = df_orders["TP"].apply(lambda x: np.nan if x == 0.0 else x)
    return df_orders.sort_values(by="Time Setup", ascending=False)


def get_positions():
    if not st.session_state.get("connected_account_login"):
        return pd.DataFrame()
    account_info_current = mt5.account_info()
    if (
        not account_info_current
        or account_info_current.login != st.session_state.connected_account_login
    ):
        return pd.DataFrame()
    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return pd.DataFrame()
    df_positions = pd.DataFrame(list(positions), columns=positions[0]._asdict().keys())
    relevant_cols = {
        "ticket": "Ticket",
        "time_msc": "Time Open",
        "type": "Type",
        "magic": "Magic",
        "symbol": "Symbol",
        "volume": "Volume",
        "price_open": "Price Open",
        "sl": "SL",
        "tp": "TP",
        "price_current": "Price Current",
        "profit": "Profit",
    }
    df_positions = df_positions[list(relevant_cols.keys())].rename(
        columns=relevant_cols
    )
    position_type_map = {mt5.POSITION_TYPE_BUY: "BUY", mt5.POSITION_TYPE_SELL: "SELL"}
    df_positions["Type"] = df_positions["Type"].map(position_type_map)
    df_positions["Time Open"] = pd.to_datetime(df_positions["Time Open"], unit="ms")
    df_positions["SL"] = df_positions["SL"].apply(lambda x: np.nan if x == 0.0 else x)
    df_positions["TP"] = df_positions["TP"].apply(lambda x: np.nan if x == 0.0 else x)
    return df_positions.sort_values(by="Time Open", ascending=False)


def get_history_trades_closed(start_date, end_date):
    if not st.session_state.get("connected_account_login"):
        return pd.DataFrame()
    account_info_current = mt5.account_info()
    if (
        not account_info_current
        or account_info_current.login != st.session_state.connected_account_login
    ):
        return pd.DataFrame()
    if isinstance(start_date, pd.Timestamp):
        start_date = start_date.to_pydatetime()
    if isinstance(end_date, pd.Timestamp):
        end_date = end_date.to_pydatetime()
    start_date_dt = datetime.combine(
        start_date.date() if isinstance(start_date, datetime) else start_date,
        datetime.min.time(),
    )
    end_date_dt = datetime.combine(
        end_date.date() if isinstance(end_date, datetime) else end_date,
        datetime.max.time(),
    )
    deals = mt5.history_deals_get(start_date_dt, end_date_dt)
    if deals is None:
        st.warning(
            f"Error al obtener deals del historial para el rango {start_date_dt.date()} - {end_date_dt.date()}: {mt5.last_error()}"
        )
        return pd.DataFrame()
    if len(deals) == 0:
        return pd.DataFrame()
    deals_df = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    deals_df = deals_df[
        (
            deals_df["entry"].isin(
                [mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT]
            )
        )
        & (deals_df["position_id"] > 0)
        & (deals_df["type"].isin([mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL]))
    ]
    if deals_df.empty:
        return pd.DataFrame()
    deals_df["time_dt"] = pd.to_datetime(deals_df["time_msc"], unit="ms")
    deals_df = deals_df.sort_values(by=["position_id", "time_dt"])
    trades_list = []
    for position_id, group in deals_df.groupby("position_id"):
        if group.empty:
            continue
        first_deal_of_position = group.iloc[0]
        last_deal_of_position = group.iloc[-1]
        trade_profit_raw_sum = group["profit"].sum()
        trade_commission_sum = group["commission"].sum()
        trade_swap_sum = group["swap"].sum()
        trade_profit_net = trade_profit_raw_sum + trade_commission_sum + trade_swap_sum
        trade_action_type = (
            "BUY" if first_deal_of_position["type"] == mt5.DEAL_TYPE_BUY else "SELL"
        )
        total_volume = first_deal_of_position["volume"]
        trades_list.append(
            {
                "Position ID": position_id,
                "Symbol": first_deal_of_position["symbol"],
                "Magic": first_deal_of_position["magic"],
                "Time Open": first_deal_of_position["time_dt"],
                "Price Open": first_deal_of_position["price"],
                "Time Close": last_deal_of_position["time_dt"],
                "Price Close": last_deal_of_position["price"],
                "Type": trade_action_type,
                "Volume": total_volume,
                "Profit": trade_profit_net,
                "Commission": trade_commission_sum,
                "Swap": trade_swap_sum,
                "Order Open": first_deal_of_position["order"],
                "Profit Raw Sum": trade_profit_raw_sum,
            }
        )
    if not trades_list:
        return pd.DataFrame()
    closed_trades_df = pd.DataFrame(trades_list)
    return closed_trades_df.sort_values(by="Time Close", ascending=False)


def calculate_kpis(closed_trades_df, initial_account_balance_for_period=None):
    if closed_trades_df.empty:
        return {
            "max_dd_percent": 0,
            "consecutive_wins": 0,
            "profit_factor": np.nan,
            "consecutive_losses": 0,
            "total_profit_period": 0,
            "num_trades": 0,
            "gross_profit": 0,
            "gross_loss": 0,
            "max_drawdown_value": 0,
            "win_rate": 0,
        }
    trades_df_sorted = closed_trades_df.sort_values(by="Time Close", ascending=True)
    current_equity_net = 0
    peak_equity_net = 0
    max_drawdown_net = 0
    total_profit_calc_period_net = trades_df_sorted["Profit"].sum()
    max_consecutive_wins = 0
    current_wins_streak = 0
    max_consecutive_losses = 0
    current_losses_streak = 0
    gross_profit_raw = 0
    gross_loss_raw = 0
    num_trades = len(trades_df_sorted)
    num_wins = 0
    for _, trade in trades_df_sorted.iterrows():
        current_equity_net += trade["Profit"]
        if current_equity_net > peak_equity_net:
            peak_equity_net = current_equity_net
        drawdown_current = peak_equity_net - current_equity_net
        if drawdown_current > max_drawdown_net:
            max_drawdown_net = drawdown_current
        profit_for_stats = trade["Profit Raw Sum"]
        if profit_for_stats > 0:
            num_wins += 1
            gross_profit_raw += profit_for_stats
            current_wins_streak += 1
            current_losses_streak = 0
            if current_wins_streak > max_consecutive_wins:
                max_consecutive_wins = current_wins_streak
        elif profit_for_stats < 0:
            gross_loss_raw += abs(profit_for_stats)
            current_losses_streak += 1
            current_wins_streak = 0
            if current_losses_streak > max_consecutive_losses:
                max_consecutive_losses = current_losses_streak
    win_rate_calc = (num_wins / num_trades * 100) if num_trades > 0 else 0
    max_dd_percent_calc = 0.0
    if max_drawdown_net > 0:
        if (
            initial_account_balance_for_period is not None
            and initial_account_balance_for_period > 0
        ):
            max_dd_percent_calc = (
                max_drawdown_net / initial_account_balance_for_period
            ) * 100
        elif peak_equity_net > 0:
            max_dd_percent_calc = (max_drawdown_net / peak_equity_net) * 100
    profit_factor_calc = np.nan
    if gross_loss_raw > 0:
        profit_factor_calc = round(gross_profit_raw / gross_loss_raw, 2)
    elif gross_profit_raw > 0:
        profit_factor_calc = np.inf
    return {
        "max_dd_percent": round(max_dd_percent_calc, 2),
        "consecutive_wins": max_consecutive_wins,
        "profit_factor": profit_factor_calc,
        "consecutive_losses": max_consecutive_losses,
        "total_profit_period": round(total_profit_calc_period_net, 2),
        "num_trades": num_trades,
        "gross_profit": round(gross_profit_raw, 2),
        "gross_loss": round(gross_loss_raw, 2),
        "max_drawdown_value": round(max_drawdown_net, 2),
        "win_rate": round(win_rate_calc, 2),
    }


def shutdown_mt5():
    if st.session_state.get("connected_account_login"):
        try:
            mt5.shutdown()
        except Exception as e:
            st.warning(f"Error al intentar desconectar de MT5: {e}")
        finally:
            st.session_state.connected_account_login = None
            st.session_state.current_account_currency = None
            st.session_state.mt5_initialized_globally = False


# MOVED FUNCTION DEFINITION EARLIER
def get_all_deals_for_period(start_datetime, end_datetime):
    if not st.session_state.get("connected_account_login"):
        return pd.DataFrame()
    deals = mt5.history_deals_get(start_datetime, end_datetime)
    if deals is None or len(deals) == 0:
        return pd.DataFrame()
    df_deals = pd.DataFrame(list(deals), columns=deals[0]._asdict().keys())
    df_deals["time_dt"] = pd.to_datetime(df_deals["time_msc"], unit="ms")
    return df_deals.sort_values(by="time_dt", ascending=True)


if "accounts_config" not in st.session_state:
    st.session_state.accounts_config = []
if "secrets_loaded" not in st.session_state:
    st.session_state.secrets_loaded = False
if "selected_account_idx" not in st.session_state:
    st.session_state.selected_account_idx = None
if "connected_account_login" not in st.session_state:
    st.session_state.connected_account_login = None
if "current_account_currency" not in st.session_state:
    st.session_state.current_account_currency = "$"
if "kpi_start_date" not in st.session_state:
    st.session_state.kpi_start_date = datetime.now().date() - timedelta(days=30)
if "kpi_end_date" not in st.session_state:
    st.session_state.kpi_end_date = datetime.now().date()
if "auto_refresh_interval" not in st.session_state:
    st.session_state.auto_refresh_interval = 40
if "selected_magic_number_kpi" not in st.session_state:
    st.session_state.selected_magic_number_kpi = "AGREGADO (CUENTA COMPLETA)"
if "mt5_initialized_globally" not in st.session_state:
    st.session_state.mt5_initialized_globally = False
if "auto_refresh_active" not in st.session_state:
    st.session_state.auto_refresh_active = False
if "track_record_grouping" not in st.session_state:
    st.session_state.track_record_grouping = "Diario"
if "track_record_initial_balance_input" not in st.session_state:
    st.session_state.track_record_initial_balance_input = None
if "track_record_selected_eas" not in st.session_state:
    st.session_state.track_record_selected_eas = []


def load_accounts_from_secrets():
    try:
        secret_accounts = st.secrets.get("mt5_account", [])
        secret_passwords = st.secrets.get("mt5_password", [])
        secret_servers = st.secrets.get("mt5_server", [])
        secret_names = st.secrets.get("mt5_name", [])
        secret_paths = st.secrets.get("mt5_path", [])
        if isinstance(secret_accounts, str):
            secret_accounts = [secret_accounts]
        if isinstance(secret_passwords, str):
            secret_passwords = [secret_passwords]
        if isinstance(secret_servers, str):
            secret_servers = [secret_servers]
        if isinstance(secret_names, str):
            secret_names = [secret_names]
        if isinstance(secret_paths, str):
            global_path_from_secrets = secret_paths.strip()
            secret_paths = [global_path_from_secrets] * len(secret_accounts)
        elif (
            isinstance(secret_paths, list)
            and len(secret_paths) == 1
            and len(secret_accounts) > 1
        ):
            global_path_from_secrets = secret_paths[0].strip()
            secret_paths = [global_path_from_secrets] * len(secret_accounts)
        if not (len(secret_accounts) == len(secret_passwords) == len(secret_servers)):
            st.warning(
                "Las listas 'mt5_account', 'mt5_password', 'mt5_server' en secrets deben tener la misma longitud."
            )
            return
        for i in range(len(secret_accounts)):
            try:
                login = int(secret_accounts[i])
                name = (
                    secret_names[i]
                    if i < len(secret_names) and secret_names[i]
                    else f"Cuenta Secreta {login}"
                )
                current_path = ""
                if (
                    i < len(secret_paths)
                    and secret_paths[i]
                    and secret_paths[i].strip()
                ):
                    current_path = secret_paths[i].strip()
                config = {
                    "name": name,
                    "login": login,
                    "password": secret_passwords[i],
                    "server": secret_servers[i],
                    "path": current_path,
                }
                existing_logins = [
                    acc["login"] for acc in st.session_state.accounts_config
                ]
                if login not in existing_logins:
                    st.session_state.accounts_config.append(config)
                else:
                    for idx, acc_cfg in enumerate(st.session_state.accounts_config):
                        if acc_cfg["login"] == login:
                            st.session_state.accounts_config[idx] = config
                            break
            except ValueError:
                st.error(
                    f"Error procesando cuenta #{i+1} de secrets: Login '{secret_accounts[i]}' inválido."
                )
            except IndexError:
                st.error(
                    f"Error de consistencia en listas de secrets para cuenta #{i+1}."
                )
    except Exception as e:
        st.error(f"Error al cargar cuentas desde secrets.toml: {e}")


if not st.session_state.secrets_loaded:
    load_accounts_from_secrets()
    st.session_state.secrets_loaded = True

st.title("📈 Dashboard MT5 Multi-Cuenta Pro")

with st.sidebar:
    st.header("Gestión de Cuentas MT5")
    with st.expander("Añadir/Actualizar Configuración Manual", expanded=False):
        cfg_name = st.text_input(
            "Nombre Descriptivo", key="cfg_name_manual", placeholder="Ej: Mi Cuenta FX"
        )
        cfg_account_str = st.text_input(
            "Nº Cuenta MT5", key="cfg_account_manual", placeholder="Ej: 123456"
        )
        cfg_password = st.text_input(
            "Contraseña MT5", type="password", key="cfg_password_manual"
        )
        cfg_server = st.text_input(
            "Servidor MT5", key="cfg_server_manual", placeholder="Ej: Broker-Server"
        )
        cfg_mt5_path = st.text_input(
            "Ruta terminal64.exe (Opcional)", key="cfg_mt5_path_manual"
        )
        if st.button("💾 Guardar Configuración Manual"):
            if cfg_account_str.isdigit():
                cfg_account = int(cfg_account_str)
                if cfg_name and cfg_account > 0 and cfg_password and cfg_server:
                    new_config = {
                        "name": cfg_name,
                        "login": cfg_account,
                        "password": cfg_password,
                        "server": cfg_server,
                        "path": cfg_mt5_path,
                    }
                    found = False
                    for i, acc in enumerate(st.session_state.accounts_config):
                        if acc["login"] == cfg_account:
                            st.session_state.accounts_config[i] = new_config
                            found = True
                            st.success(
                                f"Configuración para '{cfg_name}' ({cfg_account}) actualizada."
                            )
                            break
                    if not found:
                        st.session_state.accounts_config.append(new_config)
                        st.success(
                            f"Configuración para '{cfg_name}' ({cfg_account}) añadida."
                        )
                    st.rerun()
                else:
                    st.warning("Completa todos los campos obligatorios.")
            else:
                st.error("El nº de cuenta debe ser numérico.")
    st.markdown("---")
    if st.session_state.accounts_config:
        account_options = {
            acc["login"]: f"{acc['name']} ({acc['login']})"
            for acc in st.session_state.accounts_config
        }
        options_logins_list = list(account_options.keys())
        idx_to_select = 0
        current_selection_login_for_box = None
        if (
            st.session_state.connected_account_login
            and st.session_state.connected_account_login in options_logins_list
        ):
            current_selection_login_for_box = st.session_state.connected_account_login
        elif (
            st.session_state.selected_account_idx is not None
            and st.session_state.selected_account_idx
            < len(st.session_state.accounts_config)
            and st.session_state.accounts_config[st.session_state.selected_account_idx][
                "login"
            ]
            in options_logins_list
        ):
            current_selection_login_for_box = st.session_state.accounts_config[
                st.session_state.selected_account_idx
            ]["login"]
        if (
            current_selection_login_for_box
            and current_selection_login_for_box in options_logins_list
        ):
            idx_to_select = options_logins_list.index(current_selection_login_for_box)
        elif options_logins_list:
            st.session_state.selected_account_idx = 0
            idx_to_select = 0
        selected_login_value = st.selectbox(
            "Selecciona cuenta:",
            options=options_logins_list,
            format_func=lambda login_val: account_options.get(
                login_val, str(login_val)
            ),
            index=idx_to_select,
            key="account_selector_value",
        )
        if selected_login_value:
            selected_account_details = next(
                (
                    acc
                    for acc in st.session_state.accounts_config
                    if acc["login"] == selected_login_value
                ),
                None,
            )
            if selected_account_details:
                for i, acc_conf in enumerate(st.session_state.accounts_config):
                    if acc_conf["login"] == selected_login_value:
                        st.session_state.selected_account_idx = i
                        break
                if (
                    st.session_state.connected_account_login
                    == selected_account_details["login"]
                ):
                    st.success(f"🔌 Conectado a: {selected_account_details['name']}")
                    if st.button("🔌 Desconectar"):
                        shutdown_mt5()
                        st.rerun()
                else:
                    if st.button(f"🔌 Conectar a {selected_account_details['name']}"):
                        with st.spinner("Conectando..."):
                            if initialize_mt5(selected_account_details):
                                st.rerun()
            else:
                st.error("Detalles de cuenta no encontrados.")
    else:
        st.info("Añade una configuración de cuenta (manual o vía secrets.toml).")
    st.markdown("---")
    if st.session_state.connected_account_login:
        st.header("Configuración KPIs")
        today_date = datetime.now().date()
        kpi_start_date_val = st.date_input(
            "Fecha Inicio KPIs",
            value=st.session_state.kpi_start_date,
            max_value=today_date,
            key="kpi_start",
        )
        kpi_end_date_val = st.date_input(
            "Fecha Fin KPIs",
            value=st.session_state.kpi_end_date,
            min_value=kpi_start_date_val,
            max_value=today_date,
            key="kpi_end",
        )
        if (
            kpi_start_date_val != st.session_state.kpi_start_date
            or kpi_end_date_val != st.session_state.kpi_end_date
        ):
            st.session_state.kpi_start_date = kpi_start_date_val
            st.session_state.kpi_end_date = kpi_end_date_val
            st.rerun()
        st.header("Configuración Track Record")
        initial_balance_input = st.number_input(
            f"Balance Inicial Cuenta (para Track Record, en {st.session_state.current_account_currency})",
            min_value=0.01,
            value=(
                st.session_state.track_record_initial_balance_input
                if st.session_state.track_record_initial_balance_input is not None
                else 10000.0
            ),
            step=100.0,
            format="%.2f",
            key="tr_initial_balance_manual_input",
            help="Ingrese el balance con el que la cuenta comenzó o el balance al inicio del período más largo que desea analizar para el Track Record.",
        )
        if initial_balance_input != st.session_state.track_record_initial_balance_input:
            st.session_state.track_record_initial_balance_input = initial_balance_input
            st.rerun()
        grouping_options = ["Diario", "Semanal", "Mensual"]
        selected_grouping = st.selectbox(
            "Agrupar gráfico por:",
            options=grouping_options,
            index=grouping_options.index(st.session_state.track_record_grouping),
            key="track_record_grouping_select",
        )
        if selected_grouping != st.session_state.track_record_grouping:
            st.session_state.track_record_grouping = selected_grouping
            st.rerun()

        all_deals_for_ea_options = get_all_deals_for_period(
            datetime(2000, 1, 1), datetime.now()
        )
        track_record_ea_options = ["Balance Cuenta"]
        if not all_deals_for_ea_options.empty:
            trading_deals_for_options = all_deals_for_ea_options[
                all_deals_for_ea_options["type"].isin(
                    [mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL]
                )
            ]
            if not trading_deals_for_options.empty:
                unique_magics = sorted(trading_deals_for_options["magic"].unique())
                for magic in unique_magics:
                    if magic == 0:
                        track_record_ea_options.append("Trades Manuales (Magic 0)")
                    else:
                        track_record_ea_options.append(f"EA {magic}")

        if not st.session_state.track_record_selected_eas or not all(
            item in track_record_ea_options
            for item in st.session_state.track_record_selected_eas
        ):
            st.session_state.track_record_selected_eas = track_record_ea_options

        selected_eas_for_chart = st.multiselect(
            "Seleccionar EAs/Elementos para el gráfico:",
            options=track_record_ea_options,
            default=st.session_state.track_record_selected_eas,
            key="tr_selected_eas_multiselect",
        )
        if selected_eas_for_chart != st.session_state.track_record_selected_eas:
            st.session_state.track_record_selected_eas = selected_eas_for_chart
            st.rerun()

    st.markdown("---")
    if st.button(
        "🔄 Actualizar Manualmente",
        disabled=not st.session_state.connected_account_login,
    ):
        st.rerun()
    auto_refresh = st.checkbox(
        f"Auto-actualizar ({st.session_state.auto_refresh_interval}s)",
        value=st.session_state.auto_refresh_active,
        disabled=not st.session_state.connected_account_login,
        key="auto_refresh_cb",
    )
    st.session_state.auto_refresh_active = auto_refresh


if st.session_state.connected_account_login:
    account_info = mt5.account_info()
    if account_info and account_info.login == st.session_state.connected_account_login:
        st.subheader(f"Cuenta: {account_info.name} ({account_info.login})")
        col1, col2, col3, col4 = st.columns(4)
        currency = st.session_state.current_account_currency
        col1.metric("Balance", f"{account_info.balance:.2f} {currency}")
        col2.metric("Equidad", f"{account_info.equity:.2f} {currency}")
        col3.metric("Margen Libre", f"{account_info.margin_free:.2f} {currency}")
        col4.metric("Profit Flotante", f"{account_info.profit:.2f} {currency}")
        st.session_state.current_balance_for_kpi = account_info.balance
        st.session_state.current_equity_for_track_record = account_info.equity
    else:
        st.warning(
            f"Desincronización de cuenta o fallo al obtener datos. Verifique la conexión con MT5."
        )
        if st.session_state.connected_account_login:
            shutdown_mt5()
            st.rerun()

    tab_names = [
        "📊 KPIs Cuenta/EA",
        "📈 Posiciones",
        "📋 Órdenes",
        "🏆 Comparativa EAs",
        "🗓️ Track Record",
    ]
    tab1, tab2, tab3, tab4, tab5 = st.tabs(tab_names)

    with tab1:
        st.subheader("Key Performance Indicators (KPIs Generales)")
        if "kpi_start_date" in st.session_state and "kpi_end_date" in st.session_state:
            date_range_col, magic_selector_col = st.columns([3, 2])
            with date_range_col:
                st.markdown(
                    f"Periodo: **{st.session_state.kpi_start_date.strftime('%Y-%m-%d')}** a **{st.session_state.kpi_end_date.strftime('%Y-%m-%d')}**"
                )
            closed_trades_df_full_period = get_history_trades_closed(
                st.session_state.kpi_start_date, st.session_state.kpi_end_date
            )
            initial_balance_for_dd_calc_tab1 = 0
            if "current_balance_for_kpi" in st.session_state:
                current_bal = st.session_state.current_balance_for_kpi
                if (
                    closed_trades_df_full_period is not None
                    and not closed_trades_df_full_period.empty
                ):
                    total_profit_net_in_period_full_account = (
                        closed_trades_df_full_period["Profit"].sum()
                    )
                    initial_balance_for_dd_calc_tab1 = (
                        current_bal - total_profit_net_in_period_full_account
                    )
                elif closed_trades_df_full_period is not None:
                    initial_balance_for_dd_calc_tab1 = current_bal
            if closed_trades_df_full_period is None:
                st.error(
                    "Error al obtener el historial de trades cerrados del servidor MT5 para el periodo de KPIs."
                )
            elif "current_balance_for_kpi" not in st.session_state:
                st.warning(
                    "Esperando balance actual de la cuenta para calcular KPIs detallados."
                )
            else:
                magic_numbers_raw = []
                if not closed_trades_df_full_period.empty:
                    magic_numbers_raw = closed_trades_df_full_period["Magic"].unique()
                magic_options = ["AGREGADO (CUENTA COMPLETA)"]
                if 0 in magic_numbers_raw:
                    magic_options.append("Trades Manuales (Magic 0)")
                magic_options.extend(
                    [
                        f"EA Magic {m}"
                        for m in sorted([m for m in magic_numbers_raw if m != 0])
                    ]
                )
                if (
                    st.session_state.selected_magic_number_kpi not in magic_options
                    and magic_options
                ):
                    st.session_state.selected_magic_number_kpi = magic_options[0]
                with magic_selector_col:
                    selected_magic_display = st.selectbox(
                        "Filtrar por:",
                        options=magic_options,
                        index=(
                            magic_options.index(
                                st.session_state.selected_magic_number_kpi
                            )
                            if st.session_state.selected_magic_number_kpi
                            in magic_options
                            else 0
                        ),
                        key="magic_selector_kpi",
                    )
                if selected_magic_display != st.session_state.selected_magic_number_kpi:
                    st.session_state.selected_magic_number_kpi = selected_magic_display
                    st.rerun()
                trades_to_process_for_kpi = pd.DataFrame()
                kpi_title_suffix = ""
                if (
                    st.session_state.selected_magic_number_kpi
                    == "AGREGADO (CUENTA COMPLETA)"
                ):
                    trades_to_process_for_kpi = closed_trades_df_full_period.copy()
                    kpi_title_suffix = " (Cuenta Completa)"
                elif (
                    st.session_state.selected_magic_number_kpi
                    == "Trades Manuales (Magic 0)"
                ):
                    trades_to_process_for_kpi = closed_trades_df_full_period[
                        closed_trades_df_full_period["Magic"] == 0
                    ].copy()
                    kpi_title_suffix = " (Trades Manuales - Magic 0)"
                else:
                    try:
                        selected_m_num = int(
                            st.session_state.selected_magic_number_kpi.split(" ")[-1]
                        )
                        trades_to_process_for_kpi = closed_trades_df_full_period[
                            closed_trades_df_full_period["Magic"] == selected_m_num
                        ].copy()
                        kpi_title_suffix = f" (EA Magic {selected_m_num})"
                    except (ValueError, IndexError):
                        pass
                if trades_to_process_for_kpi.empty:
                    if (
                        st.session_state.selected_magic_number_kpi
                        == "AGREGADO (CUENTA COMPLETA)"
                        and closed_trades_df_full_period.empty
                    ):
                        st.info(
                            f"No hay trades cerrados en el periodo seleccionado para la cuenta completa."
                        )
                    elif (
                        st.session_state.selected_magic_number_kpi
                        != "AGREGADO (CUENTA COMPLETA)"
                    ):
                        st.info(
                            f"No hay trades cerrados para '{st.session_state.selected_magic_number_kpi}' en el periodo seleccionado."
                        )
                    elif closed_trades_df_full_period.empty:
                        st.info(f"No hay trades cerrados en el periodo seleccionado.")
                else:
                    kpis = calculate_kpis(
                        trades_to_process_for_kpi.copy(),
                        initial_account_balance_for_period=initial_balance_for_dd_calc_tab1,
                    )
                    st.markdown(f"#### Resultados KPIs{kpi_title_suffix}")
                    if initial_balance_for_dd_calc_tab1 > 0:
                        st.caption(
                            f"Balance inicial del período (usado para Max DD %): {initial_balance_for_dd_calc_tab1:.2f} {currency}"
                        )
                    elif kpis["max_drawdown_value"] > 0:
                        st.caption(
                            "Max DD % calculado relativo al rendimiento pico de los trades (Balance inicial del período no positivo, no aplicable, o no hubo trades en el período completo para determinarlo)."
                        )
                    kpi_cols_row1 = st.columns(4)
                    kpi_cols_row1[0].metric(
                        f"Max DD %", f"{kpis['max_dd_percent']:.2f}%"
                    )
                    kpi_cols_row1[0].metric(
                        f"Max DD (Dinero)",
                        f"{kpis['max_drawdown_value']:.2f} {currency}",
                    )
                    kpi_cols_row1[1].metric("Profit Factor", f"{kpis['profit_factor']}")
                    kpi_cols_row1[2].metric("Racha Victorias", kpis["consecutive_wins"])
                    kpi_cols_row1[3].metric(
                        "Racha Pérdidas", kpis["consecutive_losses"]
                    )
                    kpi_cols_row2 = st.columns(4)
                    kpi_cols_row2[0].metric(
                        "Total Profit Periodo (Neto)",
                        f"{kpis['total_profit_period']} {currency}",
                    )
                    kpi_cols_row2[1].metric("Trades Cerrados", kpis["num_trades"])
                    kpi_cols_row2[2].metric("Win Rate", f"{kpis['win_rate']}%")
                    kpi_cols_row2[3].metric(
                        "Gross Profit", f"{kpis['gross_profit']} {currency}"
                    )
                    with st.expander(
                        f"Ver Historial de Trades Cerrados del Periodo{kpi_title_suffix}"
                    ):
                        display_df = trades_to_process_for_kpi.copy()
                        for col_time in ["Time Open", "Time Close"]:
                            if (
                                col_time in display_df.columns
                                and not pd.api.types.is_string_dtype(
                                    display_df[col_time]
                                )
                            ):
                                display_df[col_time] = display_df[col_time].dt.strftime(
                                    "%Y-%m-%d %H:%M:%S"
                                )
                        cols_to_show = [
                            "Time Close",
                            "Symbol",
                            "Type",
                            "Volume",
                            "Price Open",
                            "Price Close",
                            "Profit",
                            "Commission",
                            "Swap",
                            "Magic",
                            "Position ID",
                        ]
                        st.dataframe(
                            display_df[
                                [c for c in cols_to_show if c in display_df.columns]
                            ],
                            use_container_width=True,
                        )
        else:
            st.info("Selecciona rango de fechas para KPIs en el panel lateral.")

    with tab2:
        st.subheader("Posiciones Abiertas")
        df_positions = get_positions()
        if df_positions is not None and not df_positions.empty:
            df_positions_display = df_positions.copy()
            if "Time Open" in df_positions_display.columns:
                df_positions_display["Time Open"] = df_positions_display[
                    "Time Open"
                ].dt.strftime("%Y-%m-%d %H:%M:%S")
            st.dataframe(
                df_positions_display,
                use_container_width=True,
                height=(len(df_positions) + 1) * 35 + 3,
            )
        elif df_positions is None:
            st.error("Error al obtener posiciones abiertas.")
        else:
            st.info("No hay posiciones abiertas.")

    with tab3:
        st.subheader("Órdenes Pendientes")
        df_orders = get_open_orders()
        if df_orders is not None and not df_orders.empty:
            df_orders_display = df_orders.copy()
            if "Time Setup" in df_orders_display.columns:
                df_orders_display["Time Setup"] = df_orders_display[
                    "Time Setup"
                ].dt.strftime("%Y-%m-%d %H:%M:%S")
            st.dataframe(
                df_orders_display,
                use_container_width=True,
                height=(len(df_orders) + 1) * 35 + 3,
            )
        elif df_orders is None:
            st.error("Error al obtener órdenes pendientes.")
        else:
            st.info("No hay órdenes pendientes abiertas.")

    with tab4:
        st.subheader("Comparativa de Rendimiento por EA")
        years_of_history_for_ea_tab = 5
        start_date_ea_history = datetime.now() - timedelta(
            days=365 * years_of_history_for_ea_tab
        )
        st.caption(
            f"Datos basados en el historial de los últimos {years_of_history_for_ea_tab} años."
        )
        full_history_trades_tab4 = get_history_trades_closed(
            start_date_ea_history, datetime.now()
        )
        initial_balance_for_dd_calc_tab4 = None
        if "current_balance_for_kpi" in st.session_state:
            current_bal_tab4 = st.session_state.current_balance_for_kpi
            if (
                full_history_trades_tab4 is not None
                and not full_history_trades_tab4.empty
            ):
                total_profit_net_in_tab4_period = full_history_trades_tab4[
                    "Profit"
                ].sum()
                initial_balance_for_dd_calc_tab4 = (
                    current_bal_tab4 - total_profit_net_in_tab4_period
                )
            elif full_history_trades_tab4 is not None:
                initial_balance_for_dd_calc_tab4 = current_bal_tab4
        if full_history_trades_tab4.empty:
            st.info(
                f"No se encontraron trades cerrados en el historial de los últimos {years_of_history_for_ea_tab} años."
            )
        elif full_history_trades_tab4 is None:
            st.error(
                f"Error al obtener historial de trades para la pestaña Comparativa EAs."
            )
        else:
            magic_numbers = sorted(
                m for m in full_history_trades_tab4["Magic"].unique() if m != 0
            )
            if not magic_numbers:
                st.info(
                    f"No hay trades de EAs (Magic Number > 0) en el historial de los últimos {years_of_history_for_ea_tab} años."
                )
            else:
                ea_kpis_list = []
                for magic in magic_numbers:
                    df_ea_trades = full_history_trades_tab4[
                        full_history_trades_tab4["Magic"] == magic
                    ].copy()
                    if not df_ea_trades.empty:
                        kpis_ea = calculate_kpis(
                            df_ea_trades,
                            initial_account_balance_for_period=initial_balance_for_dd_calc_tab4,
                        )
                        ea_kpis_list.append(
                            {
                                "EA (Magic)": magic,
                                "Trades": kpis_ea["num_trades"],
                                "Win Rate (%)": kpis_ea["win_rate"],
                                "Profit Factor": kpis_ea["profit_factor"],
                                "Max DD (%)": kpis_ea["max_dd_percent"],
                                f"Max DD ({currency})": kpis_ea["max_drawdown_value"],
                                "Racha Victorias": kpis_ea["consecutive_wins"],
                                "Racha Pérdidas": kpis_ea["consecutive_losses"],
                                f"Total Profit ({currency})": kpis_ea[
                                    "total_profit_period"
                                ],
                            }
                        )
                if ea_kpis_list:
                    df_ea_comparison = pd.DataFrame(ea_kpis_list)
                    st.dataframe(
                        df_ea_comparison.set_index("EA (Magic)"),
                        use_container_width=True,
                    )
                    with st.expander("Ver trades detallados por EA (mismo periodo)"):
                        for magic in magic_numbers:
                            df_magic_display = full_history_trades_tab4[
                                full_history_trades_tab4["Magic"] == magic
                            ].copy()
                            if not df_magic_display.empty:
                                st.markdown(f"#### EA Magic {magic}")
                                for col_time in ["Time Open", "Time Close"]:
                                    if (
                                        col_time in df_magic_display.columns
                                        and not pd.api.types.is_string_dtype(
                                            df_magic_display[col_time]
                                        )
                                    ):
                                        df_magic_display[col_time] = df_magic_display[
                                            col_time
                                        ].dt.strftime("%Y-%m-%d %H:%M:%S")
                                cols_ea_hist = [
                                    "Time Close",
                                    "Symbol",
                                    "Type",
                                    "Volume",
                                    "Price Open",
                                    "Price Close",
                                    "Profit",
                                    "Commission",
                                    "Swap",
                                    "Position ID",
                                ]
                                st.dataframe(
                                    df_magic_display[
                                        [
                                            c
                                            for c in cols_ea_hist
                                            if c in df_magic_display.columns
                                        ]
                                    ],
                                    height=200,
                                    use_container_width=True,
                                )
                else:
                    st.info("No se pudieron calcular KPIs para los EAs encontrados.")

    with tab5:
        st.subheader("Track Record General y Rendimiento de EAs")
        user_initial_balance_for_tr = (
            st.session_state.track_record_initial_balance_input
        )
        selected_eas_for_tr_chart = st.session_state.track_record_selected_eas

        if user_initial_balance_for_tr is None or user_initial_balance_for_tr <= 0:
            st.warning(
                f"Por favor, ingrese un Balance Inicial de Cuenta positivo en la sección 'Configuración Track Record' de la barra lateral para generar el gráfico de rendimiento (en {currency})."
            )
        else:
            grouping_mode = st.session_state.track_record_grouping
            end_date_tr_all_history = datetime.now()
            start_date_tr_all_history = datetime(2000, 1, 1)

            all_deals_complete_history = get_all_deals_for_period(
                start_date_tr_all_history, end_date_tr_all_history
            )

            if all_deals_complete_history.empty:
                first_deal_date_str = np.nan
                st.info("No hay historial de operaciones (deals) para esta cuenta.")
            else:
                first_deal_date = all_deals_complete_history["time_dt"].min().date()
                first_deal_date_str = first_deal_date.strftime("%Y-%m-%d")
                st.markdown(
                    f"Mostrando datos de actividad de toda la cuenta (desde {first_deal_date_str} hasta {end_date_tr_all_history.strftime('%Y-%m-%d')}), "
                    f"agrupados de forma **{grouping_mode.lower()}**. "
                    f"Cálculos basados en un Balance Inicial de Cuenta de **{user_initial_balance_for_tr:.2f} {currency}**."
                )

                trading_deals_summary = all_deals_complete_history[
                    all_deals_complete_history["type"].isin(
                        [mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL]
                    )
                    & all_deals_complete_history["entry"].isin(
                        [mt5.DEAL_ENTRY_IN, mt5.DEAL_ENTRY_OUT, mt5.DEAL_ENTRY_INOUT]
                    )
                ].copy()
                balance_ops_summary = all_deals_complete_history[
                    all_deals_complete_history["type"] == mt5.DEAL_TYPE_BALANCE
                ].copy()
                profit_all_time = 0
                deposits_all_time = 0
                withdrawals_all_time = 0
                if not trading_deals_summary.empty:
                    profit_all_time = (
                        trading_deals_summary["profit"].sum()
                        + trading_deals_summary["commission"].sum()
                        + trading_deals_summary["swap"].sum()
                    )
                if not balance_ops_summary.empty:
                    deposits_all_time = balance_ops_summary[
                        balance_ops_summary["profit"] > 0
                    ]["profit"].sum()
                    withdrawals_all_time = balance_ops_summary[
                        balance_ops_summary["profit"] < 0
                    ]["profit"].sum()

                summary_col, chart_col = st.columns([1, 2])
                with summary_col:
                    st.markdown("#### Resumen General (Toda la Cuenta)")
                    base_for_total_gain_calc = (
                        user_initial_balance_for_tr + deposits_all_time
                    )
                    if base_for_total_gain_calc <= 0:
                        base_for_total_gain_calc = 1
                    total_gain_percent = (
                        (profit_all_time / base_for_total_gain_calc) * 100
                        if base_for_total_gain_calc > 0
                        else 0
                    )
                    st.metric("Gain % (Total Cuenta)", f"{total_gain_percent:.2f}%")
                    num_days_account_life = (
                        (end_date_tr_all_history.date() - first_deal_date).days
                        if first_deal_date_str != np.nan
                        else 0
                    )
                    if num_days_account_life == 0:
                        num_days_account_life = 1
                    avg_daily_profit_total = profit_all_time / num_days_account_life
                    avg_daily_gain_percent_total = (
                        (avg_daily_profit_total / base_for_total_gain_calc) * 100
                        if base_for_total_gain_calc > 0
                        else 0
                    )
                    st.metric(
                        "Daily Avg. Gain % (Total Cuenta)",
                        f"{avg_daily_gain_percent_total:.2f}%",
                    )
                    avg_monthly_gain_percent_total = avg_daily_gain_percent_total * (
                        30.44
                    )
                    st.metric(
                        "Monthly Avg. Gain % (Total Cuenta)",
                        f"{avg_monthly_gain_percent_total:.2f}%",
                    )
                    all_closed_trades_ever = get_history_trades_closed(
                        start_date_tr_all_history.date(), end_date_tr_all_history.date()
                    )
                    if not all_closed_trades_ever.empty:
                        kpis_drawdown_total = calculate_kpis(
                            all_closed_trades_ever, user_initial_balance_for_tr
                        )
                        st.metric(
                            "Drawdown % (Total Cuenta, vs Bal. Inicial)",
                            f"{kpis_drawdown_total['max_dd_percent']:.2f}%",
                        )
                    else:
                        st.metric("Drawdown % (Total Cuenta)", "0.00%")
                    current_acc_balance = st.session_state.current_balance_for_kpi
                    st.metric(
                        "Balance Actual Real", f"{current_acc_balance:.2f} {currency}"
                    )
                    current_equity = st.session_state.get(
                        "current_equity_for_track_record", current_acc_balance
                    )
                    st.metric("Equity Actual Real", f"{current_equity:.2f} {currency}")
                    highest_balance_ever = user_initial_balance_for_tr
                    temp_running_balance_for_peak = user_initial_balance_for_tr
                    if not all_deals_complete_history.empty:
                        all_ops_sorted_for_peak = pd.concat(
                            [
                                trading_deals_summary[
                                    ["time_dt", "profit", "commission", "swap"]
                                ].assign(
                                    delta=lambda x: x["profit"]
                                    + x["commission"]
                                    + x["swap"]
                                ),
                                balance_ops_summary[["time_dt", "profit"]].rename(
                                    columns={"profit": "delta"}
                                ),
                            ]
                        ).sort_values("time_dt")
                        if not all_ops_sorted_for_peak.empty:
                            for delta_val in all_ops_sorted_for_peak["delta"]:
                                temp_running_balance_for_peak += delta_val
                                highest_balance_ever = max(
                                    highest_balance_ever, temp_running_balance_for_peak
                                )
                    if current_acc_balance > highest_balance_ever:
                        highest_balance_ever = current_acc_balance
                    st.metric(
                        "Highest Balance (Total Cuenta)",
                        f"{highest_balance_ever:.2f} {currency}",
                    )
                    st.metric(
                        "Profit (Total Cuenta)", f"{profit_all_time:.2f} {currency}"
                    )
                    st.metric(
                        "Deposits (Total Cuenta)", f"{deposits_all_time:.2f} {currency}"
                    )
                    st.metric(
                        "Withdrawals (Total Cuenta)",
                        f"{abs(withdrawals_all_time):.2f} {currency}",
                    )
                    interest_costs_total = 0
                    if not trading_deals_summary.empty:
                        interest_costs_total = (
                            trading_deals_summary["commission"].sum()
                            + trading_deals_summary["swap"].sum()
                        )
                    st.metric(
                        "Interest/Costs (Total Cuenta)",
                        f"{interest_costs_total:.2f} {currency}",
                    )
                    st.caption(f"Updated: {datetime.now().strftime('%b %d at %H:%M')}")

                with chart_col:
                    st.markdown("#### Gráfico de Rendimiento (%)")
                    chart_y_title = "% Rendimiento"
                    actual_chart_start_date = (
                        first_deal_date
                        if first_deal_date_str != np.nan
                        else start_date_tr_all_history.date()
                    )

                    if grouping_mode == "Diario":
                        freq_code = "D"
                        altair_x_config = alt.X(
                            "period_start:T",
                            title="Periodo",
                            axis=alt.Axis(format="%Y-%m-%d"),
                        )
                        date_format_tooltip = "%Y-%m-%d"
                    elif grouping_mode == "Semanal":
                        freq_code = "W-MON"
                        altair_x_config = alt.X(
                            "period_start:T", title="Periodo", timeUnit="yearweek"
                        )
                        date_format_tooltip = "%Y-W%U"
                    else:
                        freq_code = "MS"
                        altair_x_config = alt.X(
                            "period_start:T", title="Periodo", timeUnit="yearmonth"
                        )
                        date_format_tooltip = "%Y-%m"

                    chart_periods = pd.date_range(
                        start=actual_chart_start_date,
                        end=end_date_tr_all_history,
                        freq=freq_code,
                    ).to_series()
                    chart_periods = chart_periods.dt.tz_localize(None)

                    def get_period_group(dt, freq):
                        if freq == "D":
                            return dt.floor("D")
                        if freq == "W-MON":
                            return dt.to_period("W").start_time
                        if freq == "MS":
                            return dt.to_period("M").start_time
                        return dt.floor("D")

                    _all_deals_for_chart = all_deals_complete_history.copy()
                    if not _all_deals_for_chart.empty:
                        _all_deals_for_chart.loc[:, "period_group"] = (
                            _all_deals_for_chart["time_dt"].apply(
                                lambda x: get_period_group(x, freq_code)
                            )
                        )

                    _trading_deals_chart = _all_deals_for_chart[
                        _all_deals_for_chart["type"].isin(
                            [mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL]
                        )
                        & _all_deals_for_chart["entry"].isin(
                            [
                                mt5.DEAL_ENTRY_IN,
                                mt5.DEAL_ENTRY_OUT,
                                mt5.DEAL_ENTRY_INOUT,
                            ]
                        )
                    ]
                    _balance_ops_chart = _all_deals_for_chart[
                        _all_deals_for_chart["type"] == mt5.DEAL_TYPE_BALANCE
                    ]

                    chart_data_list = []
                    running_balance_chart = user_initial_balance_for_tr
                    magic_numbers_in_deals_chart = (
                        _trading_deals_chart["magic"].unique()
                        if not _trading_deals_chart.empty
                        else []
                    )
                    cumulative_ea_profits_chart = {
                        magic: 0.0 for magic in magic_numbers_in_deals_chart
                    }

                    for period_start_dt in chart_periods:
                        deals_in_this_chart_period = _trading_deals_chart[
                            _trading_deals_chart["period_group"] == period_start_dt
                        ]
                        balance_ops_in_this_chart_period = _balance_ops_chart[
                            _balance_ops_chart["period_group"] == period_start_dt
                        ]
                        period_profit_sum_chart = (
                            deals_in_this_chart_period["profit"].sum()
                            if not deals_in_this_chart_period.empty
                            else 0
                        )
                        period_comm_sum_chart = (
                            deals_in_this_chart_period["commission"].sum()
                            if not deals_in_this_chart_period.empty
                            else 0
                        )
                        period_swap_sum_chart = (
                            deals_in_this_chart_period["swap"].sum()
                            if not deals_in_this_chart_period.empty
                            else 0
                        )
                        period_balance_op_sum_chart = (
                            balance_ops_in_this_chart_period["profit"].sum()
                            if not balance_ops_in_this_chart_period.empty
                            else 0
                        )
                        running_balance_chart += (
                            period_profit_sum_chart
                            + period_comm_sum_chart
                            + period_swap_sum_chart
                            + period_balance_op_sum_chart
                        )

                        if "Balance Cuenta" in selected_eas_for_tr_chart:
                            value_to_plot_balance = (
                                (running_balance_chart - user_initial_balance_for_tr)
                                / user_initial_balance_for_tr
                            ) * 100
                            chart_data_list.append(
                                {
                                    "period_start": period_start_dt,
                                    "value": value_to_plot_balance,
                                    "type": "Balance Cuenta",
                                }
                            )

                        for magic in magic_numbers_in_deals_chart:
                            ea_name_key = (
                                f"EA {magic}"
                                if magic != 0
                                else "Trades Manuales (Magic 0)"
                            )
                            if ea_name_key in selected_eas_for_tr_chart:
                                ea_deals_this_chart_period = deals_in_this_chart_period[
                                    deals_in_this_chart_period["magic"] == magic
                                ]
                                period_ea_profit_chart = (
                                    ea_deals_this_chart_period["profit"].sum()
                                    if not ea_deals_this_chart_period.empty
                                    else 0
                                )
                                period_ea_comm_chart = (
                                    ea_deals_this_chart_period["commission"].sum()
                                    if not ea_deals_this_chart_period.empty
                                    else 0
                                )
                                period_ea_swap_chart = (
                                    ea_deals_this_chart_period["swap"].sum()
                                    if not ea_deals_this_chart_period.empty
                                    else 0
                                )
                                cumulative_ea_profits_chart[magic] += (
                                    period_ea_profit_chart
                                    + period_ea_comm_chart
                                    + period_ea_swap_chart
                                )
                                value_to_plot_ea = (
                                    cumulative_ea_profits_chart[magic]
                                    / user_initial_balance_for_tr
                                ) * 100
                                chart_data_list.append(
                                    {
                                        "period_start": period_start_dt,
                                        "value": value_to_plot_ea,
                                        "type": ea_name_key,
                                    }
                                )

                    if chart_data_list:
                        df_chart = pd.DataFrame(chart_data_list)
                        tooltip_value_format = ".2f"

                        base = alt.Chart(df_chart).encode(
                            x=altair_x_config,
                            tooltip=[
                                alt.Tooltip(
                                    "period_start:T",
                                    title="Periodo",
                                    format=date_format_tooltip,
                                ),
                                alt.Tooltip("type:N", title="Tipo"),
                                alt.Tooltip(
                                    "value:Q",
                                    title=chart_y_title,
                                    format=tooltip_value_format,
                                ),
                            ],
                        )

                        bar_chart = (
                            base.transform_filter(alt.datum.type == "Balance Cuenta")
                            .mark_bar(opacity=0.5)
                            .encode(
                                y=alt.Y("value:Q", title=chart_y_title),
                                color=alt.condition(
                                    alt.datum.value >= 0,
                                    alt.value("steelblue"),
                                    alt.value("orange"),
                                ),
                            )
                        )

                        line_chart = (
                            base.transform_filter(alt.datum.type != "Balance Cuenta")
                            .mark_line(point=True)
                            .encode(
                                y=alt.Y("value:Q", title=chart_y_title),
                                color=alt.Color(
                                    "type:N",
                                    legend=alt.Legend(title="Leyenda", orient="right"),
                                ),
                            )
                        )

                        layered_chart = (
                            alt.layer(bar_chart, line_chart)
                            .resolve_scale(y="shared")
                            .properties(
                                height=400,
                                title=f"Rendimiento de Toda la Cuenta ({grouping_mode})",
                            )
                        )
                        st.altair_chart(layered_chart, use_container_width=True)
                    elif all_deals_complete_history.empty:
                        st.info(
                            "No hay historial de operaciones (deals) para esta cuenta."
                        )
                    else:
                        st.info(
                            "No hay datos suficientes para generar el gráfico de rendimiento con la agrupación seleccionada."
                        )
else:
    st.info("👋 Bienvenido. Conecta una cuenta MT5 desde el panel lateral.")
    st.markdown("Asegúrate de que MetaTrader 5 está en ejecución y accesible.")

st.markdown("---")
st.caption(f"Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if st.session_state.get("connected_account_login") and st.session_state.get(
    "auto_refresh_active", False
):
    time.sleep(st.session_state.auto_refresh_interval)
    st.rerun()
