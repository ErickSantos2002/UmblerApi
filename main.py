import requests
import os
import re
import json
from datetime import datetime, timezone

# Imports para a API do Google Drive utilizando a conta de serviço
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

###########################################
# CONFIGURAÇÃO DO GOOGLE DRIVE (Conta de Serviço)
###########################################

# Escopo de acesso à API do Google Drive
SCOPES = ['https://www.googleapis.com/auth/drive']
# Arquivo com as credenciais da conta de serviço (ajuste o nome ou caminho se necessário)
SERVICE_ACCOUNT_FILE = 'service-account.json'
# ID da pasta no Google Drive onde os arquivos serão enviados
GOOGLE_DRIVE_FOLDER_ID = "1uAkiRE0GM3Y3JZhSZoMEdCVqhZxZQICB"

# Cria as credenciais e o serviço do Google Drive
credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
drive_service = build('drive', 'v3', credentials=credentials)

def upload_file_to_drive(file_path, folder_id, service):
    """
    Faz o upload do arquivo file_path para a pasta especificada no Google Drive.
    """
    file_metadata = {
        'name': os.path.basename(file_path),
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='text/plain')
    try:
        uploaded_file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"Arquivo '{file_path}' enviado para o Drive com ID: {uploaded_file.get('id')}")
    except Exception as e:
        print(f"Erro ao enviar o arquivo '{file_path}' para o Drive: {e}")

###########################################
# CONFIGURAÇÃO DA API EXTERNA (Ex: uTalk)
###########################################

# URL base da API externa
base_url = "https://app-utalk.umbler.com/api"

# Token atualizado da API externa
token = "Administrador-2025-01-31-2093-02-18--880D5E33498AF9F2E80A2C84CAD97FDD9864B2A9619EE5F702B98466FEE8818F"

# Organization ID
organization_id = "Z1rNHnw1mEX8IPCW"

# Pasta local onde os arquivos das conversas serão salvos
folder_name = "Conversas_Finalizadas"
os.makedirs(folder_name, exist_ok=True)  # Cria a pasta se não existir

###########################################
# FUNÇÕES AUXILIARES
###########################################

def sanitize_filename(filename):
    """Remove caracteres inválidos para nomes de arquivo."""
    return re.sub(r'[\/\\:*?"<>|]', '_', filename)

###########################################
# CARREGAR DICIONÁRIO DE MEMBROS (Members.json)
###########################################

try:
    with open("Members.json", "r", encoding="utf-8") as f:
        members = json.load(f)
    # Cria um dicionário mapeando o id do membro para o nome
    members_dict = {member["id"]: member["nome"] for member in members}
except Exception as e:
    print(f"Erro ao carregar Members.json: {e}")
    members_dict = {}

###########################################
# BUSCA E SALVA DAS CONVERSAS
###########################################

# Cabeçalhos para a requisição da API externa
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/json"
}

def get_current_date_str():
    """Retorna a data atual em UTC no formato YYYY-MM-DD."""
    return datetime.utcnow().strftime("%Y-%m-%d")

# Exemplo de uso:
current_date = get_current_date_str()

params_chats = {
    "organizationId": organization_id,
    "ChatState": "Closed",  # Conversas encerradas
    "Messages": "All",
    "OrderBy": "LastMessage",
    "Skip": 0,
    "Take": 20,
    "DateStartCreatedAtUTC": current_date + "00:00:00",
    "DateEndCreatedAtUTC": current_date + "20:00:00"
}

try:
    print("Buscando conversas finalizadas...")
    response = requests.get(f"{base_url}/v1/chats/", headers=headers, params=params_chats)
    response.raise_for_status()

    chats_data = response.json()  # Resposta completa da API

    # Extraindo os IDs das conversas e nomes dos contatos
    chat_info = [
        {
            "id": chat["id"],
            "name": sanitize_filename(chat["contact"].get("name", "Contato_Desconhecido")),
            "createdAtUTC": chat.get("createdAtUTC", "Desconhecido"),
            "closedAtUTC": chat.get("closedAtUTC", "Desconhecido"),
        }
        for chat in chats_data.get("items", [])
    ]

    print(f"Encontradas {len(chat_info)} conversas finalizadas.")

    # Para cada conversa finalizada, buscar mensagens e salvar em arquivo
    for chat in chat_info:
        chat_id = chat["id"]
        contact_name = chat["name"]  # Nome do contato, conforme a API de chat
        created_at = chat["createdAtUTC"]
        closed_at = chat["closedAtUTC"]

        # Criando o nome do arquivo (Nome do contato + Data de início)
        formatted_date = created_at.replace(":", "-")
        file_name = f"{contact_name}_{formatted_date}.txt"
        file_path = os.path.join(folder_name, file_name)

        print(f"\n🔍 Buscando mensagens da conversa de {contact_name} (ID: {chat_id})...")
        print(f"📅 Iniciada: {created_at} | Finalizada: {closed_at}")

        endpoint_messages = f"/v1/chats/{chat_id}/relative-messages/"
        params_messages = {
            "organizationId": organization_id,
            "FromEventUTC": datetime.now(timezone.utc).isoformat(),
            "Take": 50,  # Número de mensagens por conversa
            "Direction": "TakeBefore"
        }

        try:
            response_messages = requests.get(f"{base_url}{endpoint_messages}", headers=headers, params=params_messages)
            response_messages.raise_for_status()
            messages = response_messages.json().get("messages", [])

            print(f"📩 {len(messages)} mensagens encontradas na conversa de {contact_name}.")

            with open(file_path, "w", encoding="utf-8") as txt_file:
                txt_file.write(f"📌 **Conversa com: {contact_name}** (ID: {chat_id})\n")
                txt_file.write(f"📅 Iniciada: {created_at} | Finalizada: {closed_at}\n")
                txt_file.write("=" * 100 + "\n")

                for msg in messages:
                    timestamp = msg.get("eventAtUTC", "Sem data")
                    content = msg.get("content", "")
                    
                    # Nova lógica para definir o remetente
                    if msg.get("source") == "Member":
                        member_info = msg.get("sentByOrganizationMember")
                        if member_info and member_info.get("id"):
                            member_id = member_info.get("id")
                            sender = members_dict.get(member_id, "usuário desconhecido")
                        else:
                            sender = "usuário desconhecido"
                    else:
                        # Para mensagens que não foram enviadas por membros da organização, usa o nome do contato
                        sender = contact_name

                    # Formatação da mensagem de acordo com o tipo
                    if msg.get("messageType") == "Text" and content:
                        message_text = f"[{timestamp}] {sender}: {content}\n"
                    elif msg.get("messageType") == "Audio" and msg.get("file"):
                        message_text = f"[{timestamp}] {sender}: [Áudio] {msg['file'].get('url', 'Sem URL')}\n"
                    elif msg.get("messageType") == "Image" and msg.get("file"):
                        message_text = f"[{timestamp}] {sender}: [Imagem] {msg['file'].get('url', 'Sem URL')}\n"
                    elif msg.get("messageType") == "Video" and msg.get("file"):
                        message_text = f"[{timestamp}] {sender}: [Vídeo] {msg['file'].get('url', 'Sem URL')}\n"
                    elif msg.get("messageType") == "File" and msg.get("file"):
                        message_text = f"[{timestamp}] {sender}: [Arquivo] {msg['file'].get('url', 'Sem URL')}\n"
                    elif msg.get("messageType") == "Contact":
                        contact_list = msg.get("contacts", [])
                        if contact_list:
                            contact_details = []
                            for contact in contact_list:
                                name = contact.get("name", "Nome desconhecido")
                                phone_numbers = ", ".join(contact.get("phoneNumbers", ["Sem número"]))
                                contact_details.append(f"{name} - {phone_numbers}")
                            message_text = f"[{timestamp}] {sender}: [Contato] {', '.join(contact_details)}\n"
                        else:
                            message_text = f"[{timestamp}] {sender}: [Contato] Nenhuma informação disponível\n"
                    else:
                        message_text = f"[{timestamp}] {sender}: [Tipo de mensagem não identificado]\n"

                    print(f"📝 {message_text.strip()}")
                    txt_file.write(message_text)

                txt_file.write("\n" + "=" * 100 + "\n")

            print(f"✅ Conversa salva em: {file_path}")

            # Após salvar localmente, faz o upload para o Google Drive
            upload_file_to_drive(file_path, GOOGLE_DRIVE_FOLDER_ID, drive_service)

        except requests.exceptions.RequestException as e:
            print(f"⚠ Erro ao buscar mensagens da conversa {chat_id}: {e}")

    print(f"\n✅ Todas as conversas foram processadas e enviadas para o Google Drive.")

except requests.exceptions.RequestException as e:
    print(f"❌ Erro ao buscar conversas: {e}")
