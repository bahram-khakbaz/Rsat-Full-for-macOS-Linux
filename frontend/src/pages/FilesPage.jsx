import { api } from '../api.js';
import { Button } from '../components/Button.jsx';
import { Status } from '../components/Status.jsx';
import { Modal } from '../components/Modal.jsx';
import { Table } from '../components/Table.jsx';
import { Panel } from '../components/Panel.jsx';
import FileTransferPage from './FileTransferPage.jsx';

export function FilesPage(props) {
  return <FileTransferPage {...props} api={api} ui={{ Panel, Button, Modal, Table, Status }} />;
}
