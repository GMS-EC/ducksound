import { useState, useEffect } from "react";
import { ChevronRight, ChevronDown, Folder, FileMusic } from "lucide-react";
import client from "../api/client";

interface TreeNode {
  name: string;
  path: string;
  type: "folder" | "file";
  children?: TreeNode[];
  song_count?: number;
}

function TreeItem({ node, depth }: { node: TreeNode; depth: number }) {
  const [open, setOpen] = useState(false);
  const isFolder = node.type === "folder";

  return (
    <div>
      <div
        className="folder-item"
        style={{ paddingLeft: 8 + depth * 20 + "px" }}
        onClick={() => isFolder && setOpen(!open)}
      >
        {isFolder ? (
          open ? <ChevronDown size={14} className="folder-icon" /> : <ChevronRight size={14} className="folder-icon" />
        ) : (
          <span style={{ width: 14 }} />
        )}
        {isFolder ? (
          <Folder size={16} className="folder-icon" />
        ) : (
          <FileMusic size={16} className="file-icon" />
        )}
        <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{node.name}</span>
        {isFolder && node.song_count !== undefined && node.song_count > 0 && (
          <span style={{ fontSize: 11, color: "#9ca3af", marginLeft: "auto" }}>{node.song_count}</span>
        )}
      </div>
      {isFolder && open && node.children && (
        <div>
          {node.children.map((child) => (
            <TreeItem key={child.path} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function FoldersPage() {
  const [tree, setTree] = useState<TreeNode[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    client.get("/folders")
      .then((res) => setTree(res.data.tree || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "#9ca3af" }}>Cargando...</div>;

  return (
    <div className="page-wrapper">
      <div className="page-header">
        <h1 className="page-title">Explorador de carpetas</h1>
        <p className="page-subtitle">Navega por la estructura de archivos de música</p>
      </div>
      <div className="folder-tree" style={{ paddingTop: 24 }}>
        {tree.length === 0 ? (
          <p style={{ color: "#9ca3af", fontSize: 14 }}>No hay carpetas configuradas</p>
        ) : (
          tree.map((node) => <TreeItem key={node.path} node={node} depth={0} />)
        )}
      </div>
    </div>
  );
}
