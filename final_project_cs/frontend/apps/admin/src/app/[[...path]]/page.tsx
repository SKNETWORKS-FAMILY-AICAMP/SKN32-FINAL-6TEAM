import AdminApp from '../../components/AdminApp';
export default async function Page({ params }: { params: Promise<{ path?: string[] }> }) {
  const { path } = await params;
  return <AdminApp mode={process.env.NEXT_PUBLIC_ADMIN_DATA_MODE} initialPath={'/' + (path || []).join('/')} />;
}
