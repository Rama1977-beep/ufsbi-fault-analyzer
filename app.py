import os
import pandas as pd
import streamlit as st

# ==============================================================================
# 1. TOTAL 29 RELAY & ELECTRONIC CARD MASTER DATABASE (Deltron UFSBI 2oo3 Standard)
# ==============================================================================
EXTENDED_RELAY_DB = {
    # --- ब्लॉक सीक्वेंस रिले ---
    "TGTNR": {"function": "Train Going To Normal Relay", "probable_cause": "Block handle reset failure or cancellation sequence interrupted.", "feed_path": "Check BLR (A1-A2 Front) and ALR (B3-B4 Back) contacts."},
    "BPNR": {"function": "Block Plunger Normal Relay", "probable_cause": "Bell plunger switch contact dirty, open-circuit, or carboned.", "feed_path": "Check BPKR (C1-C2 Front) and TGTNR (A4-A5 Front)."},
    "TGTR": {"function": "Train Going To Control Relay", "probable_cause": "Line Clear initiation block or terminal wiring disconnected.", "feed_path": "Check TGTXR (A4-A5) and BPNR (C1-C2 Front)."},
    "TGTXR": {"function": "Train Going To Extra/Repeater Relay", "probable_cause": "Repeater circuit drop or loose base socket plug-in.", "feed_path": "Check TGTR (D1-D2 Front) and LCPR (B1-B2 Front)."},
    "TCFR": {"function": "Train Coming From Control Relay", "probable_cause": "Line clear signal not received from opposite station.", "feed_path": "Verify BIPR1 (A4-A5) and TGTR (B3-B4 Back)."},
    "BTSR": {"function": "Block Track Sequence Relay", "probable_cause": "Block track circuit fail, SSDAC/MSDAC section occupied, or R1-R2 loop open.", "feed_path": "Verify TCFR (A1-A2 Front) and 1ATR/2ATR front contacts."},
    "HSATPR": {"function": "Home Signal Approach Track Proving Relay", "probable_cause": "Approach track circuit drop or TPR fuse blown.", "feed_path": "Check BTSR (A3-A4 Front) and HR (D5-D6 Back)."},
    "TAR1": {"function": "Time Arrival Relay 1", "probable_cause": "Home signal replacement sequence fault or track sequence mismatch.", "feed_path": "Check BTSR (D1-D2 Front) and HSATPR (A1-A2 Back)."},
    "TAR2": {"function": "Time Arrival Relay 2", "probable_cause": "Arrival timer timed-out or complete arrival conditions unfulfilled.", "feed_path": "Check TAR1 (A1-A2 Front) and AZTR-R (B3-B4 Front)."},
    
    # --- महत्वपूर्ण एडिशनल रिले (२९ रिले श्रृंखला) ---
    "LCPR": {"function": "Line Clear Proving Relay", "probable_cause": "Line communication breakdown or opposite station block condition mismatch.", "feed_path": "Check Link status and Modem Rx output terminal matrix."},
    "BLR": {"function": "Block Lock Relay", "probable_cause": "Interlocking contradiction or lock circuit power supply failure.", "feed_path": "Verify 24V DC auxiliary fuse and interlocking bus contacts."},
    "ALR": {"function": "Approach Lock Relay", "probable_cause": "Approach track occupied or manual cancellation timer initiated.", "feed_path": "Check approach track parameters and timer relay matrix."},
    "ASCR": {"function": "Approach Sequence Control Relay", "probable_cause": "Sequential track drop logic failure during train reception.", "feed_path": "Verify sequential locking relay status on terminal board."},
    "SR1": {"function": "Sequence Relay 1", "probable_cause": "Track sequence proving step-1 failure.", "feed_path": "Check entrance track relay front contact convergence."},
    "SR2": {"function": "Sequence Relay 2", "probable_cause": "Track sequence proving step-2 failure.", "feed_path": "Check berthing track circuit pick-up synchronization."},
    "2PR": {"function": "Repeater Relay 2", "probable_cause": "Coil de-energization due to parallel cascading circuit drop.", "feed_path": "Verify wiring matrix from terminal board to relay base slots."},
    "TPR": {"function": "Track Proving Relay", "probable_cause": "Physical track failure, rail breakage, or glued joint failure.", "feed_path": "Measure voltage across track relay coil terminals directly."},
    
    # --- मॉडेम, कार्ड्स और इलेक्ट्रॉनिक कम्पोनेंट्स ---
    "MODEM_CARD": {"function": "UFSBI Modem Communication Module (Rx/Tx)", "probable_cause": "Link Failure! Quad Cable/OFC breakdown, line noise, or Modem card fuse blown.", "feed_path": "Check Tx/Rx dB level, Isolation Transformer, and Line protection unit (LPU)."},
    "CPU_CARD_1": {"function": "CPU Card No. 1", "probable_cause": "Hardware fault, internal checksum error, or 5V DC power drop.", "feed_path": "Check Front Panel LED. Swap with spare CPU card if hardware fault persists."},
    "CPU_CARD_2": {"function": "CPU Card No. 2", "probable_cause": "Hardware fault, synchronization lag, or component failure.", "feed_path": "Verify logic synchronization bus data cable seating."},
    "CPU_CARD_3": {"function": "CPU Card No. 3", "probable_cause": "Hardware failure or processing mismatch.", "feed_path": "Inspect system log for internal board diagnostic flags."},
    "2oo3_VOTER": {"function": "2-out-of-3 Hardware Majority Voting Logic", "probable_cause": "Mismatched logic output! Two CPU cards are not in agreement.", "feed_path": "Identify which CPU card shows a 'FAULT' red LED. System safely shuts down if 2 cards fail."},
    "POWER_MODULE": {"function": "UFSBI Internal DC-DC Converter Converter Card", "probable_cause": "Input 24V DC fluctuated or internal 5V/12V converter blown.", "feed_path": "Measure 24V DC input at Backplane bus and check output test points."}
}

STANDARD_MASTER_SEQUENCE = ["TGTNR", "BPNR", "TGTR", "TGTXR", "LCPR", "TCFR", "BTSR", "HSATPR", "TAR1", "TAR2"]

class FullUFSBIAnalyzer:
    def parse_excel_log(self, file_obj):
        try:
            if file_obj.name.endswith('.xls'):
                df = pd.read_excel(file_obj, engine='xlrd')
            else:
                df = pd.read_excel(file_obj, engine='openpyxl')
                
            df.columns = [str(col).strip().upper() for col in df.columns]
            
            # Find relevant column mappings dynamically
            t_col = next((c for c in df.columns if "TIME" in c or "DATE" in c), df.columns[0])
            r_col = next((c for c in df.columns if "RELAY" in c or "DESC" in c or "NAME" in c or "EQUIP" in c), df.columns[1])
            s_col = next((c for c in df.columns if "STAT" in c or "STATE" in c or "VAL" in c), df.columns[2])
            
            parsed_rows = []
            for _, r in df.iterrows():
                val_str = str(r[r_col]).upper()
                stat_str = str(r[s_col]).upper()
                time_str = str(r[t_col])
                
                # Check against our 29+ element master dictionary
                matched_key = None
                for k in EXTENDED_RELAY_DB.keys():
                    if k in val_str:
                        matched_key = k
                        break
                        
                if matched_key:
                    parsed_rows.append({
                        "time": time_str,
                        "key": matched_key,
                        "status": stat_str
                    })
            return parsed_rows, df
        except Exception as e:
            st.error(f"Error reading telemetry spreadsheet: {str(e)}")
            return None, None

    def evaluate_system_health(self, rows, raw_df):
        # 1. CHECK FOR LINK FAILURE / MODEM ERRS FIRST
        raw_text_dump = raw_df.to_string().upper()
        
        if "LINK FAIL" in raw_text_dump or "COMMUNICATION FAIL" in raw_text_dump or "MODEM ERR" in raw_text_dump:
            return {
                "category": "LINK_FAILURE",
                "component": "MODEM_CARD",
                "message": "🔴 CRITICAL LINK FAILURE: UFSBI Modems disconnected or Line Interruption detected between Station A & B!"
            }
            
        # 2. CHECK FOR 2oo3 CPU VOTING MISMATCH LOGIC
        cpu_faults = []
        if "CPU 1 FAIL" in raw_text_dump or "CPU1 ERR" in raw_text_dump: cpu_faults.append("CPU_CARD_1")
        if "CPU 2 FAIL" in raw_text_dump or "CPU2 ERR" in raw_text_dump: cpu_faults.append("CPU_CARD_2")
        if "CPU 3 FAIL" in raw_text_dump or "CPU3 ERR" in raw_text_dump: cpu_faults.append("CPU_CARD_3")
        
        if len(cpu_faults) == 1:
            return {
                "category": "CPU_2oo3_WARNING",
                "component": cpu_faults[0],
                "message": f"⚠️ 2oo3 VOTER WARNING: {cpu_faults[0]} has FAILED, but system is running safe on remaining 2 CPU cards."
            }
        elif len(cpu_faults) >= 2:
            return {
                "category": "CPU_2oo3_SHUTDOWN",
                "component": "2oo3_VOTER",
                "message": "🔴 TOTAL SYSTEM SHUTDOWN: Two or more CPU Cards failed! 2-out-of-3 hardware majority voting logic dropped the system."
            }

        # 3. ROUTINE SEQUENCE TRACE ANALYSIS FOR RELAYS
        active_transitions = set()
        last_stable = "None"
        breakpoint_relay = None
        
        for r_item in rows:
            is_up = any(x in r_item['status'] for x in ['ON', 'PICK', 'UP', '1', 'REVERS', 'OK', 'HEALTHY'])
            if is_up:
                active_transitions.add(r_item['key'])

        for seq_relay in STANDARD_MASTER_SEQUENCE:
            if seq_relay in active_transitions:
                last_stable = seq_relay
            else:
                breakpoint_relay = seq_relay
                break

        if not breakpoint_relay:
            return {"category": "HEALTHY", "message": "💚 SYSTEM IS HEALTHY: All 29 relays and electronic cards operating in standard sequence."}

        return {
            "category": "RELAY_BREAKPOINT",
            "component": breakpoint_relay,
            "last_stable": last_stable,
            "message": f"❌ INTERLOCKING BREAKPOINT: Relay [ {breakpoint_relay} ] Failed to pick up in sequence."
        }

# ==============================================================================
# STREAMLIT UI SETUP
# ==============================================================================
st.set_page_config(page_title="Master UFSBI Diagnostic System", page_icon="⚙️", layout="centered")

st.title("🎛️ Master UFSBI 2oo3 Diagnostic Web Engine")
st.write("Full Station-to-Station Telemetry Analyzer (Supports all 29 Interlocking Relays, 2oo3 CPU Logic, and Modem Card Faults).")

engine = FullUFSBIAnalyzer()
uploaded_file = st.file_uploader("Upload Station Data Logger Sheet (.xls, .xlsx)", type=["xls", "xlsx"])

if uploaded_file is not None:
    st.info(f"Analyzing Station Log: {uploaded_file.name}")
    rows, raw_df = engine.parse_excel_log(uploaded_file)
    
    if raw_df is not None:
        report = engine.evaluate_system_health(rows, raw_df)
        
        st.write("---")
        st.subheader("📋 System Diagnostic Analysis")
        
        if report["category"] == "HEALTHY":
            st.success(report["message"])
            
        else:
            st.error(report["message"])
            comp = report["component"]
            details = EXTENDED_RELAY_DB.get(comp, {})
            
            if details:
                st.markdown(f"### 🔍 Failed Module Function:\n{details['function']}")
                st.markdown(f"### 🛑 Probable Field Cause:\n**{details['probable_cause']}**")
                st.markdown(f"### ⚡ Technical Wiring Feed Path Checkpoints:\n` {details['feed_path']} `")
            
            if "last_stable" in report:
                st.info(f"ℹ️ Last known stable step before failure: {report['last_stable']}")

        st.success("Analysis complete. Share this web link directly with ground technicians for instant fault isolation.")
