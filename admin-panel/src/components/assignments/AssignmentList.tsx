import {
    List,
    Datagrid,
    TextField,
    DateField,
    NumberField,
    Filter,
    NumberInput
} from 'react-admin';
import { BulkDownloadAction } from './BulkDownloadAction';

const AssignmentFilters = [
    <NumberInput source="min_score" label="Min Score (>=)" alwaysOn />
];

export const AssignmentList = () => (
    <List filters={AssignmentFilters}>
        <Datagrid bulkActionButtons={<BulkDownloadAction />}>
            <TextField source="user_profiles.email" label="User Email" />
            <TextField source="title" />
            <TextField source="grade_classification" label="Grade" />
            <NumberField source="overall_score" label="Score" />
            <TextField source="brief_text" label="Requirements" style={{ maxWidth: 200, WebkitLineClamp: 2, display: '-webkit-box', overflow: 'hidden', WebkitBoxOrient: 'vertical' }} />
            <TextField source="assignment_text" label="Solution" style={{ maxWidth: 200, WebkitLineClamp: 2, display: '-webkit-box', overflow: 'hidden', WebkitBoxOrient: 'vertical' }} />
            <DateField source="created_at" showTime />
        </Datagrid>
    </List>
);
