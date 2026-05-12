from pathlib import Path

import httpx
from fastmcp.tools import tool

from tools.client import query


def _attachment_fields() -> str:
    return """
      id
      publicId
      extension
      sizeBytes
      filename
      originalAssetUrl
      __typename
    """


@tool
async def get_transaction_attachment_upload_info(transaction_id: str) -> dict:
    """Get Monarch's signed upload parameters for a transaction attachment.

    Args:
        transaction_id: Transaction UUID from get_transactions.
    """
    query_text = """
    mutation Common_GetTransactionAttachmentUploadInfo($transactionId: UUID!) {
      getTransactionAttachmentUploadInfo(transactionId: $transactionId) {
        info {
          path
          requestParams {
            timestamp
            folder
            signature
            api_key
            upload_preset
          }
        }
      }
    }
    """
    return await query(
        "Common_GetTransactionAttachmentUploadInfo",
        query_text,
        {"transactionId": transaction_id},
    )


@tool
async def get_transaction_attachment(attachment_id: str) -> dict:
    """Get a transaction attachment's download URL.

    Args:
        attachment_id: Attachment UUID from get_transaction.
    """
    query_text = """
    query Mobile_GetAttachmentDetails($attachmentId: UUID!) {
      transactionAttachment(id: $attachmentId) {
        id
        originalAssetUrl
        __typename
      }
    }
    """
    return await query("Mobile_GetAttachmentDetails", query_text, {"attachmentId": attachment_id})


@tool
async def add_transaction_attachment_metadata(
    transaction_id: str,
    filename: str,
    public_id: str,
    extension: str,
    size_bytes: int,
) -> dict:
    """Attach an already-uploaded asset to a transaction.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        filename: Display filename.
        public_id: Uploaded asset public ID returned by Monarch's upload host.
        extension: File extension without the leading dot.
        size_bytes: Uploaded file size in bytes.
    """
    query_text = f"""
    mutation Common_AddTransactionAttachment($input: TransactionAddAttachmentMutationInput!) {{
      addTransactionAttachment(input: $input) {{
        attachment {{ {_attachment_fields()} }}
        errors {{ message __typename }}
        __typename
      }}
    }}
    """
    return await query(
        "Common_AddTransactionAttachment",
        query_text,
        {
            "input": {
                "transactionId": transaction_id,
                "filename": filename,
                "publicId": public_id,
                "extension": extension,
                "sizeBytes": size_bytes,
            }
        },
    )


@tool
async def upload_transaction_attachment(
    transaction_id: str,
    file_path: str,
    filename: str | None = None,
    content_type: str | None = None,
) -> dict:
    """Upload a local file and attach it to a transaction.

    Args:
        transaction_id: Transaction UUID from get_transactions.
        file_path: Local path to upload.
        filename: Optional display filename. Defaults to the local basename.
        content_type: Optional MIME type for the upload request.
    """
    path = Path(file_path).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"Attachment file not found: {path}")

    upload_info = await get_transaction_attachment_upload_info(transaction_id)
    info = ((upload_info.get("data") or {}).get("getTransactionAttachmentUploadInfo") or {}).get("info")
    if not info:
        raise RuntimeError(f"Monarch did not return upload info: {upload_info}")

    display_name = filename or path.name
    extension = path.suffix[1:].lower()
    upload_url = info["path"]
    if upload_url.startswith("//"):
        upload_url = f"https:{upload_url}"
    elif upload_url.startswith("/"):
        upload_url = f"https://api.cloudinary.com{upload_url}"
    params = info["requestParams"]

    with path.open("rb") as file_obj:
        files = {"file": (display_name, file_obj, content_type or "application/octet-stream")}
        async with httpx.AsyncClient() as client:
            upload_resp = await client.post(upload_url, data=params, files=files, timeout=120)
            if upload_resp.is_error:
                raise RuntimeError(f"Attachment upload failed: {upload_resp.status_code} {upload_resp.text}")
            upload_data = upload_resp.json()

    public_id = upload_data.get("public_id")
    if not public_id:
        raise RuntimeError(f"Upload succeeded but did not return public_id: {upload_data}")

    result = await add_transaction_attachment_metadata(
        transaction_id=transaction_id,
        filename=display_name,
        public_id=public_id,
        extension=extension,
        size_bytes=path.stat().st_size,
    )
    result["upload"] = {
        "public_id": public_id,
        "secure_url": upload_data.get("secure_url"),
        "bytes": upload_data.get("bytes"),
    }
    return result


@tool
async def delete_transaction_attachment(attachment_id: str) -> dict:
    """Delete a transaction attachment.

    Args:
        attachment_id: Attachment UUID from get_transaction.
    """
    query_text = """
    mutation Web_TransactionDrawerDeleteAttachment($id: UUID!) {
      deleteTransactionAttachment(id: $id) {
        deleted
        __typename
      }
    }
    """
    return await query("Web_TransactionDrawerDeleteAttachment", query_text, {"id": attachment_id})
