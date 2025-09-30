# backend/agents/nodes/salvar_node.py
from ..state import MindmapState
from ...utils.logger import logger
from ...services.file_manager import save_mmd_file
import os

async def salvar_mindmap_node(state: MindmapState) -> MindmapState:
    """
    Salva os arquivos .mmd gerados.
    """
    logger.info("Salvando mapas mentais...")
    
    try:
        arquivos_salvos = []
        
        # Pega o nome base do HTML (sem extensão)
        html_base = os.path.splitext(state["html_filename"])[0]
        
        # Salva cada parte processada
        for parte in state["partes_processadas"]:
            # Nome do arquivo: base_parte01.mmd, base_parte02.mmd, etc
            filename = f"{html_base}_parte{parte['parte_numero']:02d}.mmd"
            
            filepath = save_mmd_file(
                filename=filename,
                content=parte["mapa_gerado"],
                metadata={
                    "ramo_direito": state["ramo_direito"],
                    "topico": state["topico"],
                    "parte_titulo": parte["parte_titulo"],
                    "parte_numero": parte["parte_numero"],
                    "aprovado": parte["aprovado"],
                    "nota_geral": parte.get("nota_geral"),
                    "tentativas": parte["tentativas"]
                }
            )
            
            arquivos_salvos.append(filepath)
            logger.success(f"Salvo: {filename}")
        
        state["status"] = "concluido"
        state["logs"].append({
            "node": "salvar_mindmap",
            "arquivos_salvos": arquivos_salvos,
            "total": len(arquivos_salvos)
        })
        
        logger.success(f"Processamento concluído! {len(arquivos_salvos)} arquivos salvos.")
        return state
        
    except Exception as e:
        logger.error(f"Erro ao salvar arquivos: {str(e)}")
        state["status"] = "erro"
        state["erro_msg"] = str(e)
        return state