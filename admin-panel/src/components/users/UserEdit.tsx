import {
    Edit,
    SimpleForm,
    TextInput,
    SelectInput,
    NumberInput,
    BooleanInput,
} from 'react-admin';

export const UserEdit = () => (
    <Edit>
        <SimpleForm>
            <TextInput source="email" disabled />
            <SelectInput
                source="subscription_tier"
                choices={[
                    { id: 'Free', name: 'Free' },
                    { id: 'Basic', name: 'Basic' },
                    { id: 'Standard', name: 'Standard' },
                    { id: 'Premium', name: 'Premium' },
                    { id: 'Ultimate', name: 'Ultimate' },
                ]}
            />
            <NumberInput source="word_balance" />
            <NumberInput source="grading_balance" />
            <BooleanInput source="is_admin" />
            <BooleanInput source="is_banned" />
        </SimpleForm>
    </Edit>
);
